"""Evidence-led matching against the owner-reviewed Strain Master.

Never approve fuzzy guesses. Only exact canonical/approved-alias matches,
or mechanically parsed titles whose resulting strain matches, are publishable.
"""
import difflib
import re
import unicodedata

BRAND_PREFIXES = (
    "redwood county weed management", "trailhead cannabis company",
    "trailhead cannabis", "trailhead", "elevated botanicals",
    "elevate botanicals", "native cuts", "verist fields", "mr. birch",
    "mr birch", "little sticks", "little stick", "big sticks", "big stick",
    "looner", "mn loon", "mnl", "r & d pharms", "r & d farms",
    "dizgo collective", "dizgo", "float cannabis", "good green",
    "rythm", "dogwalkers", "unbound", "flör", "flor", "cannabis",
)
NOISE = re.compile(
    r"^(?:flower(?:[- ]?ix)?|pre[- ]?rolls?(?:[- ]?ix)?|vape(?:[- ]?ix)?|"
    r"concentrates?|distillate|infused|premium|mixed buds?|mini buds?|"
    r"whole flower|ground flower|raw|indica|sativa|hybrid|"
    r"(?:\d+(?:\.\d+)?\s*(?:g|gm|grams?|oz|ct|pk|pack))|"
    r"(?:\d+\s*[x×]\s*\d+(?:\.\d+)?\s*g))$", re.I
)
PREFIX = re.compile(
    r"^(?:(?:offer\s+conditions\s+apply|offer\s+buy\s+\d+|on sale|"
    r"\$\d+(?:\.\d+)?\s*off)\s+)+", re.I
)
WEIGHT_END = re.compile(
    r"\s*(?:[-–,(]?\s*\d+(?:\.\d+)?\s*(?:g|gm|gram|grams|oz|ct|pk|pack)"
    r"(?:\s*[x×]\s*\d+)?)\s*[),-]*$", re.I
)
FORMAT_END = re.compile(
    r"\s*[-–]?\s*(?:flower|pre[- ]?rolls?|mini buds?|premium flower|"
    r"whole flower|mixed buds?|live resin|live rosin|infused)\s*$", re.I
)

def key(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", value).strip(" .-|")

def cleanup(value):
    text = PREFIX.sub("", str(value or "").strip())
    for _ in range(6):
        prev = text
        text = WEIGHT_END.sub("", text).strip(" -|()")
        text = FORMAT_END.sub("", text).strip(" -|()")
        text = re.sub(r"\s+", " ", text)
        if text == prev:
            break
    return text.strip(" -|()")

def title_candidates(title, brand=""):
    """Conservative alternate parses, returned in reproducible priority order."""
    seen = set()
    for raw in [title]:
        pieces = [p.strip() for p in re.split(r"\|", str(raw or "")) if p.strip()]
        proposals = [cleanup(raw)]
        for p in pieces:
            if not NOISE.fullmatch(cleanup(p)):
                proposals.append(cleanup(p))
        # Only remove recognizable brand prefixes, never arbitrary words.
        names = [str(brand or "").strip(), *BRAND_PREFIXES]
        for part in list(proposals):
            for label in sorted(set(names), key=len, reverse=True):
                if not label:
                    continue
                if part.casefold().startswith(label.casefold() + " "):
                    proposals.append(cleanup(part[len(label):]))
        for p in proposals:
            p = cleanup(p)
            normalized = key(p)
            if normalized and normalized not in seen and not NOISE.fullmatch(p):
                seen.add(normalized)
                yield p

def resolve_master(*, proposed, raw_title, brand, canonical, aliases,
                   matched_aliases=None):
    """Resolve exact first, then structured alternatives, then suggest only."""
    matched_aliases = matched_aliases or {}
    for candidate in [proposed, *title_candidates(raw_title, brand),
                      *title_candidates(proposed, brand)]:
        for parsed in title_candidates(candidate, brand):
            normalized = key(parsed)
            if normalized in canonical:
                return dict(status="approved", strain=canonical[normalized],
                            method="master_exact" if parsed == proposed else "parsed_master_exact",
                            parsed=parsed)
            if normalized in aliases:
                return dict(status="approved", strain=aliases[normalized],
                            method="approved_alias", parsed=parsed)
            if normalized in matched_aliases:
                approved = matched_aliases[normalized]
                if key(approved) in canonical:
                    return dict(status="approved", strain=canonical[key(approved)],
                                method="owner_rule_master_match", parsed=parsed)
    candidates = list(title_candidates(proposed, brand)) + list(title_candidates(raw_title, brand))
    proposal = next((c for c in candidates if key(c)), str(proposed or ""))
    suggestions = difflib.get_close_matches(key(proposal), list(canonical), n=3, cutoff=.72)
    return dict(status="review", strain=str(proposed or "").strip(),
                method="unresolved_after_reparse", parsed=proposal,
                suggestions=[canonical[s] for s in suggestions])
