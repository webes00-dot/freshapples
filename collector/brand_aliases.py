"""Brand-label aliases. Never use brand normalization alone to merge offers."""
import re
import unicodedata

def canonical_brand(value):
    raw = " ".join(str(value or "").split()).strip()
    # User-approved rule: Emerald Farms plus any collaborator is Emerald Farms.
    # Includes the expanded Emerald Fire Farms spelling already in the pilot.
    if re.match(r"(?i)^emerald(?:\s+fire)?\s+farms(?:\s*\+\s*.+)?$", raw):
        return "Emerald Farms"
    simple = re.sub(r"[^a-z0-9]+", " ", "".join(c for c in unicodedata.normalize("NFKD", raw.casefold()) if not unicodedata.combining(c))).strip()
    if simple in ("lakeside", "lakeside canna", "lakeside cannabis", "lakeside cana"):
        return "Lakeside Cannabis"
    if simple in ("campfire lake leaf", "lake leaf", "lakeleaf"):
        return "Campfire Cannabis"
    if simple in ("laketown", "laketown farms", "oma"):
        return "Laketown Farms"
    if simple == "native care":
        return "Native Care"
    if simple in ("northpark", "north park", "northpark cannabis co", "northpark cannabis company", "north park cannabis co", "north park cannabis company"):
        return "Northpark"
    if simple in ("smiile", "smile", "smiiles", "smiles"):
        return "SMIILE"
    if simple in ("sappy pappy", "verist fields"):
        return "Verist Fields"
    if simple == "unwind cultivation" or simple == "unwind":
        return "Unwind"
    if simple in ("campfire", "campfire cannabis"):
        return "Campfire Cannabis"
    if simple in ("redwood", "redwood county weed management"):
        return "Redwood County Weed Management"
    if simple in ("flor", "flor fina", "flor fina cannabis", "flor fina by flor"):
        return "FLÖR"
    if simple in ("valhalla", "vahalla", "vahalla cannabis", "vahalla confections", "valhalla cannabis", "valhalla cannabis co", "valhalla cannabis company", "valhalla confections", "valhalla farms", "valhalla cannabis collective"):
        return "Valhalla"
    if simple in ("r d farms", "r d pharms", "r and d farms", "r and d pharms", "rd farms", "rd pharms"):
        return "R & D Farms"
    if simple in ("float canna", "float cannabis", "float cannabis co", "float canna co", "float cannabis company"):
        return "Float Cannabis"
    if simple in ("dizgo", "dizgo collective"):
        return "Dizgo Collective"
    return raw
