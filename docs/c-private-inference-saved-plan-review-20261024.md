# Private inference saved-plan review - 24 October 2026

Historical pre-apply record at 23:00 UTC. The later user-approved apply and read-only configuration verification are recorded in the [actual deployment report](c-private-inference-deployed-20261024.md). The observations below retain their original pre-apply scope.

The second real GCP private-inference plan passed **13/13 checks** at
`2026-10-23T23:00:15.360525+00:00` (24 October Melbourne): **four creates, nine
no-ops**, with zero other changes, drift, warnings, failed checks or unknown
security fields. Source and authoritative state remained unchanged during
planning. **This plan has not been applied or authorized for execution.**

Source: `3dd63c805b625fb3b378ac977d51c6959d599f0c`.
Saved binary SHA-256:
`988d8f63902c705443d70d53b03ebc30440b281f8445d6f78b443e24f64ec518`.

Selected observations are in the
[review evidence](../evidence/c-private-inference-saved-plan-review-20261024.json).
Full plans, state, checkpoint hashes/lineage, policies and logs remain private.
Subsequent source/evidence delivery targets the approved
[private repository](https://github.com/xihan-u/aussie-ecoguard-fit3184-a2-private).

## Exact proposed increment

The target remains `ecoguard-fit3184-a2-2026` / `995070689587`, `us-central1`.
The existing seven identity resources and two registry resources remain no-op.
The four proposed additions under `module.ecoguard` are:

| Resource | Proposed scope |
| --- | --- |
| `google_project_service.required["run.googleapis.com"]` | Run API |
| `google_service_account.runtime[0]` | Dedicated `ecoguard-inference` runtime account, without a new project role |
| `google_cloud_run_v2_service.inference[0]` | Private `ecoguard-inference` service using the verified image |
| `google_cloud_run_v2_service_iam_member.invoker[0]` | Sole `roles/run.invoker` member: the existing dedicated AWS invoker service account |

Image:
`us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb`.
Its retained successful publication proves the remote manifest/config bytes;
the plan preparation checked that evidence's continuity through the refresh
checkpoint. See the [actual image publication](c-private-image-published-20261024.md).

The service requires IAM authentication, HTTP/1 on port 8080, the fixed runtime
account, actual Cognito/bucket wiring and the locked v3 manifest. Limits are four
CPUs (startup CPU boost enabled), 8 GiB, request concurrency one, minimum zero, automatic service/revision
maximum one, platform timeout 360 seconds and application deadline 240 seconds.
Personal deletion protection is false for later reviewed cleanup. The plan adds
no model bucket, public invoker, key, arbitrary environment or AWS activation.
These limits do not prove cloud performance or establish a hard spending cap.

## Retained failure and exact state checkpoint

The first private-service plan, SHA-256
`480db4587f5f8a73708afd4565752f5eb63f09b5f640e0f7508b88c21fecc7b7`,
was blocked at **11/13** checks. It left state unchanged and was never applied.
The unresolved field was `template[0].containers[0].ports[0].name`; the provider
also reported the repository metadata changed by image publication.

The source now explicitly specifies `name="http1"` alongside the existing port
8080. The gate additionally requires that protocol and still rejects unknown
values. The repository checkpoint was handled separately through the exact
refresh-only binary
`c56a85845bc415daff55ff1302ee7aab9b52dcd5c0da50f59021b1e47e955b6c`.
It applied with exit **0** at `2026-10-23T22:59:34.964517+00:00`, retaining nine
resources and advancing state serial **11 -> 12**. Its only resource-value
changes were Terraform `labels: null -> {}` and repository `update_time`:

- Previous: `2026-10-23T22:17:27.541917Z`.
- Published-image observation: `2026-10-23T22:42:43.012721Z`.

The existing provider-managed label remained intact. No cloud resource, IAM,
API or runtime was modified, and no apply retry occurred. Private A/B backups
and an attestation bind the exact saved binary, state hashes, lineage and serials.
The forward plan gate was not weakened to ignore drift.

After that checkpoint passed, the controlled checkout moved from `00d58e0` to
`3dd63c8`. State, provider lock and `.gitignore` remained unchanged across that
source transition; the `services/` and `config/` trees had no differences.
The second plan uses that exact checkpoint and release, preserving the blocked
first plan and all earlier deployment/publication reports.

## Pending execution boundary

The prepared [apply helper](../scripts/apply_personal_gcp_private_inference_plan.py)
and [HTTP verification helper](../scripts/verify_personal_gcp_private_inference_http.py)
do not authorize execution. A **new actual user approval** is still required for
the four resources, new service-level invoker access, startup compute, and
Google's automatic Run service agent with `roles/run.serviceAgent`. That Google
managed role is additional to the four Terraform resource entries.

If separately included in that approval, the HTTP helper permits exactly three
checks without retries: anonymous `GET /healthz`, operator-authenticated
`GET /healthz`, and authenticated `POST /v1/warmup`. A cold warmup can download
the 15 locked artifacts, totaling 2,229,943,281 bytes, and load both real models.
No HTTP check or warmup has run under this plan. Startup, access rejection and
model readiness must be reported separately; AWS-role federation, media inference
and full assignment acceptance remain unverified. AWS's 55-resource foundation
continues to be paused.

Additional personal spend remains **A$0**. A fresh official Credits-page reload
at `2026-10-23T23:01:35Z` confirmed positive eligible existing trial credit; the
amount and billing identifiers remain private. Funding must still cover the
bounded execution window. Credits expire **28 October 2026**, and cleanup remains
due by **27 October Melbourne** unless another funded period is verified.
Minimum zero, maximum one and billing alerts do not guarantee a hard spending
stop. No automatic cleanup is claimed.

Prepared with Codex assistance.
