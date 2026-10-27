# Personal GCP deployment custody and stages

The approved private inference service is deployed in **ecoguard-fit3184-a2-2026** / **995070689587**, `us-central1`. The exact saved plan applied once with exit 0. A separate complete read-only configuration audit passed at `2026-10-23T23:26:51.282549Z`. There are **13 managed resources**, state serial **17**: seven identity, two registry and four runtime resources.

See the [actual deployment report](../../../../docs/c-private-inference-deployed-20261024.md) and [selected evidence](../../../../evidence/c-private-inference-deployed-20261024.json). Deployment readiness is separate from HTTP/model testing and AWS-role federation. AWS remains paused; full media processing and assignment acceptance are unverified.

## Current release and authoritative state

The state-owning CloudShell checkout is fixed at `3dd63c805b625fb3b378ac977d51c6959d599f0c`. Its existing backend is:

`~/ecoguard-c-personal-20261023/source/infra/gcp/environments/personal/state/terraform.tfstate`

The post-apply state SHA-256 is `f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad`. Original pre/post backups, lineage, plans, logs, full policies and the actual approval remain private. Git does not transfer state. Use one operator; do not initialize a second owner or import the historical team state.

Keep the Terraform 1.17.0 / Google 7.46.1 signed provider lock. Before any future plan, verify the live operator/project, source, default workspace, backend, state hash/lineage/serial and a retained backup. Current local source/evidence delivery may advance beyond the deployed release; that does not update CloudShell or deployed resources.

**Always pass the intended stage and immutable image to a future plan.** The source default remains `identity`; Terraform does not remember previous CLI inputs. Omitting them from the current thirteen-resource state proposes destructive removals. Do not accept those as routine changes.

## Historical bounded increments

| Stage | Actual transition | Managed additions |
| --- | --- | --- |
| `identity` | Applied: 0 to 7 | Restricted AWS WIF and invoker identity |
| `registry` | Applied: 7 to 9 | Registry API and private Docker repository |
| `private-inference` | Applied: 9 to 13 | Run API, dedicated runtime account, private service and sole service-level invoker grant |

The seven-resource [foundation](../../../../docs/c-personal-foundation-deployed-20261024.md), [registry deployment](../../../../docs/c-registry-deployed-20261024.md), [image publication](../../../../docs/c-private-image-published-20261024.md), and [13/13 saved-plan review](../../../../docs/c-private-inference-saved-plan-review-20261024.md) retain their historical observations. The earlier first runtime plan was blocked at 11/13, never applied; explicit `http1` plus a separately reviewed state-only publication metadata refresh resolved that planning gap. Refresh changed only repository `labels` and `update_time` before the approved runtime plan, without changing cloud resources or IAM.

The first-create `check_plan.py` and forward-increment `check_runtime_plan.py` are intentionally strict historical plan gates. The latter accepts exactly 7-to-9 or 9-to-13 forward transitions, not arbitrary updates from the current thirteen-resource state. Future wiring, reverse cleanup or provider/state remedies require a new bounded saved-plan review; do not weaken these gates to fit unrelated changes.

## Current service boundary

The actual Ready URL is `https://ecoguard-inference-adlnb7yumq-uc.a.run.app`, revision `ecoguard-inference-00001-bwg`. Its approved image is:

`us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb`

The sole service-level invoker is `ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`. Existing WIF still accepts only normalized AWS assumed role `arn:aws:sts::011154879765:assumed-role/ecoguard3184-personal-lambda`. CloudShell/root is a different identity; do not broaden WIF for testing.

Run uses `ecoguard-inference@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`, with no new assigned project/repository/ancestor role or own IAM bindings. The verified configuration requires IAM invocation, HTTP/1 port 8080, fixed model/Cognito/media environment, four CPUs with startup boost, 8 GiB, concurrency one, automatic minimum zero/maximum one at service and revision, platform timeout 360s and application deadline 240s. No extra commands, volumes, public invoker or custom audience is permitted. The unused GCS model bucket remains omitted; the locked manifest downloads pinned HTTPS artifacts with exact hashes/sizes.

Postchecks retained three observed differences rather than changing the deployment: canonical service IAM name serialization, two extra Google-managed service-agent project roles, and an unprivileged default Compute account. The [deployment report](../../../../docs/c-private-inference-deployed-20261024.md) describes their exact audit evidence and the original approval scope variance. No postcheck performed a grant or state update. All three project-listed accounts have zero user-managed keys, and the default account has zero assigned roles in captured policies and zero own IAM bindings; Run does not use it.

## Bounded HTTP/model validation

The [first actual anonymous request](../../../../docs/c-private-http-first-attempt-20261024.md) returned a platform-style 404 on `/healthz` and stopped the test before authenticated calls or warmup. It is inconclusive for IAM denial. Non-z `/health` and `/ready` aliases are prepared in source and verified offline; they are not yet deployed by this record.

The user explicitly authorized exactly three requests without retry: anonymous `GET /healthz`, operator-authenticated `GET /healthz`, and authenticated `POST /v1/warmup {}` with a 270-second client cap. The [HTTP helper](../../../../scripts/verify_personal_gcp_private_inference_http.py) requires the actual successful configuration audit, original approval, immutable plan/image/state and fresh eligible-credit evidence. It uses the existing operator identity without new grants, impersonation, static keys or persisted tokens.

The cold warmup may download 15 locked artifacts totaling **2,229,943,281 bytes**. Report its actual outcome separately from startup readiness. Even a successful warmup does not prove AWS-role token exchange, real cloud media inference, video processing, browser CORS or two-user acceptance. The earlier [local real-model smoke](../../../../docs/c-local-real-model-smoke-20261024.md) is local evidence only.

These frozen helpers and results are single-execution evidence artifacts. Do not rerun an apply, overwrite a failed summary, delete an attempt marker or infer permission from a committed helper. The final read-only inventory audit normalizes only the exact canonical service path in a deep copy and preserves all prior evidence.

## Cost, cleanup and delivery

Additional personal-spend limit is **A$0**. Existing eligible credits expire **28 October 2026**; review and clean up by **27 October Melbourne** unless a separately verified funded period is available. Minimum zero/maximum one and billing alerts are not hard spending caps; registry storage persists. No automatic cleanup is configured.

Personal deletion protection is false to allow a reviewed reverse plan. Preserve restore artifacts and state custody before cleanup; never clear the image or revert the stage as an informal pause command. A new reverse review must distinguish resources removed from Terraform state, APIs left enabled by `disable_on_destroy=false`, Google-managed role grants and actual registry content cleanup.

Source and safe evidence are delivered to the approved [private repository](https://github.com/xihan-u/aussie-ecoguard-fit3184-a2-private). Credentials, full state/plans/policies, approval receipts, billing data and raw logs stay outside Git. Group/teaching access and the earlier public repositories require separate handoff.

Prepared with Codex assistance. Current configuration is verified; remaining integration outcomes require their own actual evidence.
