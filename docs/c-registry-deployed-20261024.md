# Private registry deployed - 24 October 2026

The approved registry increment was applied successfully in
`ecoguard-fit3184-a2-2026` / `995070689587`. GCP now has **nine managed resources**:
the existing seven identity resources and two registry additions. The frozen
helper returned `registry-only-apply-and-verification-passed` at
`2026-10-23T22:18:01.336086+00:00` (24 October Melbourne).

The private standard Docker repository is `us-central1/ecoguard`. At that
verification time it was empty: **no image had been published and no runtime
had been activated**. Image transfer/publication is a separate step and is not
claimed by this record. The AWS 55-resource foundation remains paused.

Selected non-secret observations are in the
[deployment evidence](../evidence/c-registry-deployed-20261024.json). The
[saved-plan review](c-registry-saved-plan-review-20261024.md) retains its earlier
pre-apply facts; its `applyExecuted=false` describes that earlier observation.
Full plans, state, IAM snapshots, approval records and logs remain private.

## Exact execution and result

| Item | Applied value or observed result |
| --- | --- |
| Controlled source | `00d58e0e8c65321cc759d575eafaba801c1e8253` |
| Saved plan SHA-256 | `0f62543fe74a7b0fc71e9e8c2b1930de853448d1ab4c257b9d215399c9d5ba86` |
| Terraform actions | Two creates; existing seven identity resources unchanged |
| Added API | `artifactregistry.googleapis.com` |
| Added repository | `us-central1/ecoguard`, `DOCKER`, `STANDARD_REPOSITORY` |
| Apply | Exit 0; no retry |
| Post-apply state | Captured privately; nine managed resources |
| User-managed service-account keys | Zero |

The [frozen apply helper](../scripts/apply_personal_gcp_registry_plan.py) was
fetched from `88d88609ce8e8cbfe7fcc0df4ffe278f3da25bcb`, with SHA-256
`3dd73904148060c0c6a457f1aed4523936fbfed1476a354ef8149248d10b7cbc`.
It required the actual matching approval record, rechecked the selected source,
target, unchanged prior state and exact saved binary, then applied that binary
once. It preserved post-apply state and completed live configuration verification.
Fetching the helper did not replace the controlled source checkout.

The only observed project IAM addition was Google's expected Artifact Registry
service-agent role, `roles/artifactregistry.serviceAgent`. That automatic setup
was included in the approved scope. The existing WIF provider and sole invoker
service-account grant remained unchanged. No manual project-wide role or new
Cloud Run invocation grant was introduced by this increment.

## State custody and next increment

The existing GCP CloudShell personal backend remains authoritative under
`~/ecoguard-c-personal-20261023/source/infra/gcp/environments/personal/`.
Retain the nine-resource state and its private backup, with one operator. Git
shares source and selected evidence, not this state. The controlled checkout
remains at `00d58e0` for this applied increment.

The root defaults to `identity`; after this deployment, omitting the intended
stage can propose deleting the registry. Pass `deployment_stage=registry` for a
current-stage review, or use the separately reviewed `private-inference` increment
with its actual verified registry digest. Do not use an empty backend, import old
team state, repeat the seven-resource first-plan gate, or rerun the two-create
registry gate against the now-nine-resource state.

Before private inference, publish and independently verify the exact approved
image, then prepare a new saved plan expecting **four creates and nine no-ops**:
the Run API, dedicated runtime service account, private service and its single
service-level invoker grant. That access and compute require their own concrete
execution review. This registry result does not establish authenticated warmup,
Cloud Run model capacity, Lambda-role token exchange or real media processing.

The existing credit expires **28 October 2026**, and additional personal spend
remains **A$0**. Keep the operator-owned cleanup boundary at **27 October
Melbourne** unless another funded period is independently verified. Neither an
empty repository nor minimum instances zero guarantees zero future charges after
image publication. No cleanup automation or account-wide spending stop is claimed.
No balance, billing-account identifier or credential is included in this report.

Prepared with Codex assistance. Registry creation is separate from runtime and
full assignment acceptance.
