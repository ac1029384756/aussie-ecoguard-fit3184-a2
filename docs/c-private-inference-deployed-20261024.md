# Private inference service deployed, 24 October 2026

The approved saved plan was applied **once, exit 0**, creating four managed resources alongside the prior nine unchanged resources. A separate read-only audit passed at `2026-10-23T23:26:51.282549+00:00` (24 October Melbourne), confirming the private service, current ready revision, immutable image, IAM, WIF and zero user-managed keys. AWS remains paused. This record covers deployment and configuration; HTTP/model outcomes are recorded separately.

Source: `3dd63c805b625fb3b378ac977d51c6959d599f0c`.
Saved binary SHA-256: `988d8f63902c705443d70d53b03ebc30440b281f8445d6f78b443e24f64ec518`.
See the historical [13/13 saved-plan review](c-private-inference-saved-plan-review-20261024.md) and [actual deployment evidence](../evidence/c-private-inference-deployed-20261024.json). Full state, logs, policies and approval records remain private.

| Verified setting | Actual observation |
| --- | --- |
| Target | `ecoguard-fit3184-a2-2026` / `995070689587`, `us-central1` |
| Managed state | 13 resources; serial 17; same lineage and prior nine resource values |
| Service URL | `https://ecoguard-inference-adlnb7yumq-uc.a.run.app` |
| Ready revision | `ecoguard-inference-00001-bwg`; all traffic to this current revision |
| Image | Approved private Artifact Registry image at digest `sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb` |
| Service invoker binding | Sole service-level `roles/run.invoker` member is `ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com` |
| Runtime account | `ecoguard-inference@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`; no assigned project/repository/ancestor role or own IAM binding |
| Capacity | 4 CPU, 8 GiB, startup CPU boost, concurrency 1, minimum 0 / maximum 1 at service and revision |
| Protocol/deadlines | HTTP/1 port 8080; platform 360s / application 240s |
| Other boundaries | Invoker IAM enabled; fixed environment; no extra commands, volumes, VPC, custom audiences or public invoker; existing WIF unchanged |

## Retained postcheck failures and observed automatic changes

The original apply succeeded at `23:07:53.566104Z`, but its postcheck stopped because the provider stored the IAM grant's service name as its full canonical path. Google provider **7.46.1** intentionally canonicalizes this field in its [service IAM implementation](https://github.com/hashicorp/terraform-provider-google/blob/v7.46.1/google/services/cloudrunv2/iam_cloud_run_v2_service.go). A read-only adapter normalizes only that exact project/region/service path on a deep copy. It neither edits state nor loosens the forward-plan gate.

Two subsequent read-only checks retained failures while resolving additional observed differences. There was no repeated apply or resource patch. The completed audit preserves the original apply summary, both earlier audit summaries, all private artifacts and their hashes.

The actual project IAM delta contained **three** additions and no removals:

| Google-managed agent suffix after `service-995070689587@` | Project role | Audit timestamp (UTC) |
| --- | --- | --- |
| `containerregistry.iam.gserviceaccount.com` | `roles/containerregistry.ServiceAgent` | `23:06:03.544765Z` |
| `gcp-sa-pubsub.iam.gserviceaccount.com` | `roles/pubsub.serviceAgent` | `23:06:05.345511Z` |
| `serverless-robot-prod.iam.gserviceaccount.com` | `roles/run.serviceAgent` | `23:06:06.940033Z` |

Only the Run agent was individually listed in the original approval. The two extra agents are explicitly recorded as a **scope variance**, with no claim of individual preapproval. Eleven retained audit events show Google `service-agent-manager@system.gserviceaccount.com` making the three exact ADDs during the same Run API activation operation. The verifier made no new grant. Repository and ancestor IAM edges were unchanged. Google's [service-agent reference](https://docs.cloud.google.com/iam/docs/service-agents) lists these identities/roles, and its [role-manager explanation](https://docs.cloud.google.com/iam/docs/service-account-types#role-manager) describes automatic role grants. Service-agent roles are powerful; this observation does not authorize grants to application accounts or people.

The standard default Compute account `995070689587-compute@developer.gserviceaccount.com` also appeared. Its exact creation request/response occurred inside that activation window, but the creation event has no actor identity, which remains unknown. The audit verifies its enabled identity, zero assigned roles in every captured policy, zero own IAM bindings and zero user-managed keys. Run uses the dedicated runtime account instead. All three project-listed accounts were checked for user-managed keys.

The final [read-only inventory verifier](../scripts/verify_personal_gcp_private_inference_after_apply_inventory.py) retains the strict original state, image, IAM, WIF, readiness and environment checks, with these precisely documented observations. Local negative checks reject wrong service/project/region, public invokers, other roles, extra accounts and keys. They do not substitute for the actual cloud audit.

## Custody, funding and remaining validation

The existing CloudShell backend remains authoritative. Its post-apply state SHA-256 is `f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad`. Read-only audits changed neither state nor release source. Do not initialize another backend, replay the saved apply, omit stage/image inputs, or replace private checkpoints with Git files.

The user explicitly approved three bounded HTTPS checks: anonymous health denial, operator-authenticated health and one warmup capped at 270 client seconds. Their result is separate from deployment readiness. This record proves neither actual AWS-role federation nor model inference, browser CORS, video processing or full assignment acceptance. The AWS 55-resource application stays paused.

Existing eligible credits were rechecked before execution; financial amounts and billing identifiers remain private. Additional personal-spend limit is **A$0**, credits expire **28 October**, and review/cleanup is due by **27 October Melbourne**. Minimum zero and maximum one are resource limits, not a hard account-wide cost cap. Registry storage persists, and no automatic cleanup is configured.

Prepared with Codex assistance.
