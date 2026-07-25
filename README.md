# ADRC SPHERE — Synthetic Research Data Hub (portal)

Public-facing portal for the **Stanford ADRC SPHERE** dataset — a fully *synthetic*
version of the Stanford Alzheimer's Disease Research Center cohort (644 participants,
9 modalities) that researchers can explore, query, and download **without an IRB
amendment or data request**. A Data Use Agreement applies.

## Contents
- `index.html` — the single-page portal (data availability, explorer, AI analysis agent, downloads).
- `data/parquet/` (~350 MB) — the columnar data layer queried in-browser via DuckDB-WASM; powers the data-extract and download features. **Included in this repo.**
- `data/dd/`, `data/*.js`, `data/*.json.gz` — data dictionary and dataset summaries used by the explorer. **Included.**
- `sphere_visualization.html` — SPHERE visualization.
- `scripts/` — helper scripts.

The site is **self-contained** — everything needed to serve it is in this repo. (The raw
synthetic source CSVs are intermediate build artifacts, **not** required to run the site,
so they are not included.)

## Deploy
A static site — no build step. Serve the repo contents from any web host that supports
**HTTP byte-range requests** (standard Apache / nginx / CDN); the in-browser DuckDB-WASM
data extract range-reads the Parquet files, so range support and concurrency are required.

Stanford Alzheimer's Disease Research Center · He Lab. Synthetic data only — no real patient information.
