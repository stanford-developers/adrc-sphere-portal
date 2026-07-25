# ADRC SPHERE — Synthetic Research Data Hub (portal)

Public-facing portal for the **Stanford ADRC SPHERE** dataset — a fully *synthetic*
version of the Stanford Alzheimer's Disease Research Center cohort (644 participants,
9 modalities) that researchers can explore, query, and download **without an IRB
amendment or data request**. A Data Use Agreement applies.

- `index.html` — the single-page portal (data availability, explorer, AI agent, downloads).
- `data/*.js`, `data/*.json.gz` — dataset summaries + data dictionary used by the explorer.
- `sphere_visualization.html` — 3-D SPHERE visualization.
- `scripts/` — helper scripts (data-injection scripts excluded from the repo).

## Data note
The large data layers are **not** in this repo (too large for git / GitHub file limits):
- `data/parquet/` (~350 MB) — the columnar extract layer queried in-browser via DuckDB-WASM.
- `data/sphere/` (~1.6 GB) — raw synthetic CSVs.

These are deployed to the hosting server (Stanford AFS) alongside the site.

## Deploy
Content is published to Stanford AFS:
```
rsync -avz --progress --exclude 'data/sphere/' \
  --exclude 'scripts/inject_data.py' --exclude 'scripts/inject_dd.py' \
  ./ zihuai@cardinal.stanford.edu:~/WWW/adrc-sphere/
```

Stanford Alzheimer's Disease Research Center · He Lab. Synthetic data only — no real patient information.
