# Project map

- API: `api/server.py`; V2: `api/v2_routes.py`; Atlas: `api/atlas_routes.py`.
- Atlas web UI: `static/atlas.html`, `static/atlas.js`, `static/atlas.css`; state/data: `data/atlas/` (large, inspect narrowly).
- Pipeline: `ingestion/` → `vector/` → `clustering/` → `matching/` → `synthesis/` → `dispatch/`; daemon: `worker/stream_daemon.py`.
- Canonical V2 persistence and domain logic: `storage_v2/`; legacy domain models: `core/`.
- Apple client: `ios/NewsStreamApp/`.
- Focused tests: Atlas `python3 -m unittest tests.test_atlas_routes`; V2 storage `python3 -m unittest tests.test_storage_v2`; architecture `python3 -m unittest tests.test_new_architecture`; web reliability `python3 -m unittest tests.test_frontend_api_reliability`.
- Never bulk-read `data/`, `build/`, `ios/build_derived_data/`, `static/vendor/`, `__pycache__/`, or `.env`.
