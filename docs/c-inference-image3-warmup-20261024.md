# Image3 authenticated model warmup, 24 October 2026

The single authenticated `POST /v1/warmup` returned **HTTP 200** and verified model readiness at `2026-10-24T01:31:50.273912+00:00`. It took `87.694` seconds within the `270`-second timeout; the response was `237` bytes. This is selected evidence from the parent agent's actual official CloudShell/UI observation, rather than a raw-summary copy or an independent live check. See the [selected evidence](../evidence/c-inference-image3-warmup-20261024.json).

| Verified result | Actual observation |
| --- | --- |
| Project / region | `ecoguard-fit3184-a2-2026` / `us-central1` |
| Ready revision | `ecoguard-inference-00003-jwb` |
| Model readiness | `models.ready = true`; `detector` and `embedding` loaded |
| Locked manifest | `ecoguard-models-2026-10-08-v3` |
| Feature version | `siglip2-base-256-animal-crop-v3:3f9f96cb90da5dbc758b01813f2f6f1aee24c1ab:rgb-exif-animal-crop-text64-lowercase-v3` |
| State / source / IAM | Unchanged; state serial `21`, source `ac7757717486b3db2da8c955ebffcc01f6807724` |
| Request accounting | One new request; five total across retained batches; two total warmup POST attempts |

This operation made no GET, anonymous request, retry, IAM/API change or AWS action. Its authentication token was not persisted. The earlier image2 warmup `401`/`97`-byte response and original anonymous `/healthz` `404` remain preserved; the successful attempt has its own evidence directory.

The retained summary SHA-256 is `3bfcd99e4f8cc61bf77a45136405d1089a06acc8fd53b134dcb95f4875ffb425`; the warmup input manifest is `62c5b097fe89154413e76c137bae77b6869695fecd949ccdaa73ffc9c9bd1ae2`. The companion JSON also binds the exact helper, task record, immutable image and preceding successful apply. Full state, policies, raw logs, funding details and authorization quotes remain private.

This establishes successful authenticated model warmup. Image inference, retrieval and cross-cloud processing still need separate actual acceptance results. Additional personal-spend limit remains **A$0**; credits expire **28 October**, with review/cleanup due by **27 October Melbourne**. No automatic cleanup is configured.

Prepared with Codex assistance.
