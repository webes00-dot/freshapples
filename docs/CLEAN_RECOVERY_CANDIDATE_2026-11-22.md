# Clean recovery candidate — 2026-11-22

**Candidate ZIP**: `MNtrees_Clean_Recovery_Candidate_2026-11-22.zip` (saved in the user's ChatGPT Library as a private artifact, not deployed). The ZIP contains 225 files with SHA-256 manifest, updated pricing line-chart page, Python collector, JavaScript frontend, rules, tests, configuration, published site build and scan workflows.

**Build verification**
- `bash build.sh` succeeded, creating `dist/`.
- Python collector suite: 163/163 tests passed.
- Node test suite: 3/3 passed.
- Built catalog: 2,248 offers, 281 retailers, 80 brands.
- No references to `rcwm56283` remain in the candidate's source text.
- The old handoff/Pilot README was removed and replaced with release-gated current architecture notes.

**Architecture restrictions**
- This ZIP descends from the Nov 20 verified developer handoff and **does not yet contain all changes from the Nov 22 live production Worker static asset bundle**.
- Public frontend current-state assets are recovered separately in `recovery/live-2026-11-22/`.
- Current production Worker sources, including private Admin Worker, and D1 table snapshots are kept in private Cloudflare KV namespace `mntrees-private-recovery-snapshots`, not in the public GitHub repository.
- The new D1 databases are native to the current architecture and not migrated from V1.
- A new clean GitHub -> preview -> production pipeline and database restore test remain pending.
- **No live deployment is authorized until current-design parity, current data and private-code recovery, and staged release verification pass.**

**Pricing chart update in candidate**
- Replaces bar/reference image and several disconnected observation bars with one monthly 3-series SVG line chart.
- Uses separate labelled value axes for flower/pre-rolls and concentrates to keep all series legible.
- Starts plotted x-axis at first real observed month August 2025 to remove the dead region back to August 2023.
- Preserves source/evidence in `data/market-price-monthly.json` without drawing missing months as observations.
