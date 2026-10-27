# Private inference HTTP repair result

The bounded batch completed at 00:26:53.250425 UTC on 24 October 2026. Anonymous `GET /health` returned **403**; the existing operator-authenticated health request returned **200** and the exact locked model manifest. Authenticated `POST /v1/warmup` returned **401** in 1.279 seconds, so model startup was **not verified**. No automatic retry followed.

The original anonymous `/healthz`404 remains unchanged. Across both batches there were four HTTP requests and one warmup POST attempt. Full postchecks verified source, state and IAM unchanged; no tokens were persisted, permissions changed or AWS runtime activated.

Private summary: `~/ecoguard-c-personal-20261023/private-inference-http-20261024-2/summary.json`, SHA256 `089f36206bced20d7419828be6afea37bec8f419ca098490e536d37a12c255cf`. The companion evidence JSON selects the actual request outcomes; it is not the raw private summary.

The source diagnosis points to the app parsing a forwarded service bearer before its private Cloud Run adapter. [Google documents that ingress consumes the service header](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent) while preserving independent user authorization. This supports the diagnosis; the exact forwarded header shape was not captured. A repair must retain private IAM, exact invoker scope, Oracle/local verification and Cognito checks, then receive its own new bounded validation record.

The prepared code now selects the private Cloud Run adapter before parsing the consumed service header, while retaining `K_SERVICE`, private IAM and independent Cognito checks. Local/Oracle verification is unchanged. The five-case local ASGI observer run passed; an earlier4/5 result and the separate single-case pass are retained. Verification inside a newly built image and actual cloud model validation remain pending.
