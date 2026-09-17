# V2 reconciliation

| Finding | Status | Active path / files | Remaining work |
| --- | --- | --- | --- |
| Unknown publication dates were replaced by ingestion time | FIXED | `storage_v2/v1_adapter.py`, `storage_v2/content.py` | Native connectors should provide source timestamps directly. |
| Event identity was RAM-only | PARTIAL | `storage_v2/runtime.py`, `storage_v2/events.py`, `storage_v2/shadow.py` | Deterministic title-window resolution needs entity and embedding candidate signals. |
| Claims/citations were generated without grounded provenance | PARTIAL | `storage_v2/runtime.py`, `storage_v2/truth.py`, `storage_v2/generated.py` | Deterministic title evidence is conservative; richer extraction needs reviewed proposals. |
| Summary could silently become factual truth | FIXED | `storage_v2/generated.py`, `storage_v2/runtime.py` | Model-based grounded generation is intentionally not enabled. |
| Personalization was bypassed by the feed path | PARTIAL | `storage_v2/runtime.py`, `storage_v2/personalization.py`, `api/v2_routes.py` | V2 feed is available separately; legacy UI still reads V1. |
| Feedback did not create durable explainable learning signals | PARTIAL | `api/v2_routes.py`, `storage_v2/runtime.py` | iOS/web clients still need to emit all interaction types. |
| Delivery had no durable idempotence boundary | PARTIAL | `storage_v2/personalization.py`, `storage_v2/runtime.py` | Channel-specific V2 notification dispatcher remains disabled. |
| Source independence inferred from URL count | FIXED | `storage_v2/truth.py`, `storage_v2/runtime.py` | Independence remains `unknown` until explicit provenance is available. |
| V1/V2 rollout lacked a reversible path | PARTIAL | `storage_v2/config.py`, `worker/stream_daemon.py`, `api/v2_routes.py` | Enable `NEWSSTREAM_V2_CANONICAL_WRITE_ENABLED` then `NEWSSTREAM_V2_READ_ENABLED` only after local validation. |
| iOS runs a divergent information engine | NOT FIXED | iOS remains unchanged deliberately | Migrate its read path to `/api/v2` in a dedicated rollout. |
| X/Reddit connector coverage/constraints | PARTIAL | Existing V1 connectors preserved | No unsupported scraping was added. |

No automated validation was executed for this change set at the user’s request.
