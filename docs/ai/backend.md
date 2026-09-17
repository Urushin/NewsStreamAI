# Backend boundaries

FastAPI serves legacy, V2, streaming, and Atlas routes. Trace the mounted router in `api/server.py` before changing an endpoint.

V1 pipeline modules remain active. `storage_v2/` adds SQLite-backed identity, events, truth/provenance, generated content, personalization, and reversible shadow/canonical paths. Treat `docs/v2_reconciliation.md` as the current status ledger. Do not enable `NEWSSTREAM_V2_CANONICAL_WRITE_ENABLED` or `NEWSSTREAM_V2_READ_ENABLED` without dedicated validation.

Atlas is a bounded feature: start with `api/atlas_routes.py`, its three `static/atlas.*` files, and `tests/test_atlas_routes.py`. Read `data/atlas/` by exact file only. Preserve API contracts across web and Apple clients.
