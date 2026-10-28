# C static frontend: actual saved-plan review

The frontend container and a separate Terraform root are prepared. A real
Terraform 1.17.0 plan was generated in the existing GCP Cloud Shell and reviewed
locally on 28 October 2026. No image was published and no plan was applied.

| Reviewed item | Actual result |
| --- | --- |
| Project / region | `ecoguard-fit3184-a2-2026` / `us-central1` |
| Resolved project number | `995070689587` |
| Managed changes | 3 creates, 0 updates, 0 deletes |
| Creates | `ecoguard-frontend` service account; `ecoguard-web` service; that service's public invoker binding |
| Dedicated runtime account | No project roles assigned by this root |
| Public access | `allUsers`, `roles/run.invoker`, on `ecoguard-web` only |
| Resource limits | Service and revision min0/max1; 1 CPU; 256 MiB; request-based CPU; no startup boost |
| Image | Static frontend, immutable manifest `sha256:d12130aa3869398d68bf60d580db256e6abd99e7a6ffe2f5c71950d82709d458` |
| State owner | Separate `frontend-review-20261027-1/root/state/frontend.tfstate` under the existing Cloud Shell task directory |
| Saved binary plan SHA-256 | `b772797b2b0b7b92457afed36ca4b944d39113660e3a8e80356f62f46fddc1bc` |
| Plan JSON SHA-256 | `1ed186394f99979d4b548b31f94fc523eb29bdeb44dfdd4d0be51c4f83c074a6` |

The original checker stopped because this native plan retains the resolved
`data.google_project.current` only in `prior_state`. It is consumed by a resource
precondition. The checker now accepts either native location, requires the
actual project ID and number in every occurrence, and continues to reject any
prior managed resource. The original plan was not regenerated or altered.
The original checker, failure receipt, source manifest, binary plan and JSON
are preserved outside Git. The corrected checker passed the real plan and
rejected eleven mutated copies, including wrong identity, extra resources,
deletion, broader public access, a model image, always-running instances and
failed/incomplete plan checks.

At `2026-10-28T01:16:29Z`, a fresh cloud read confirmed the same authorized
operator, unchanged private inference IAM, no deployed `ecoguard-web`, and an
unchanged inference state SHA-256:
`8fceea80600b2b02caea3402951d8f7954c975845b3503522be69b69f2881358`.
This root does not manage private inference, project IAM, AWS, signup, API,
queue consumers, model requests, or media tests.

## Deployment is pending

The last successfully loaded credit view showed an end date of 28 October.
Today's credit page did not finish loading, so eligible funding is unverified.
The additional personal-spend limit remains A$0. Resource scaling limits do
not guarantee zero charges. Do not publish the image or apply this plan until
funding and retention/cleanup are reviewed and the concrete public-access action
is approved. Recheck cloud identity, plan freshness, service absence and private
inference IAM at execution time; regenerate and review if cloud state changed.

After a funded, approved deployment, verify the actual HTTPS URL, assets,
health and SPA routes. Then prepare a separate AWS CORS/API/signup plan using
that exact origin. Existing one-image test permissions are exhausted; this
preparation does not authorize another media run. Neither the frontend's local
checks nor this read-only plan establish cloud signup, login or media success.

See [selected evidence](../evidence/c-frontend-plan-20261028.json) and
[deployment instructions](../infra/gcp/environments/frontend/README.md).
