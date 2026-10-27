# Personal paused foundation deployed - 24 October 2026

The authorized AWS foundation and GCP identity-only resources now exist. AWS has
**55 managed resources**, with **40/40 live configuration checks passed**. GCP has
**seven managed identity resources**, with its actual provider and sole service-account
grant checked. Application processing remains paused. This is infrastructure and
identity evidence, not completed cross-cloud application acceptance.

The selected non-secret results are in
[the deployment evidence](../evidence/c-personal-foundation-deployed-20261024.json).
The [first-plan review](c-personal-first-plans-20261024.md) is the earlier pre-apply
snapshot. Full plans, state, credentials and credit balances are not published.

| Target | Actual result | Execution source |
| --- | --- | --- |
| AWS `011154879765 / us-east-1` | 52 initial resources, then three recovered mappings; 55 total | Initial `fdfaf23`, recovery `2936764` |
| GCP `ecoguard-fit3184-a2-2026 / 995070689587` | Seven identity-only resources; apply exit 0 | `fdfaf23` |

## AWS recovery and preserved pause

The initial approved binary plan was applied and returned exit 1: AWS rejected
only the three disabled SQS mappings because their maximum concurrency of two
exceeded their target functions' reserved concurrency of zero. The other 52
resources were retained, with no tainted instances. Commit `2936764` omits the
mapping scaling block while paused and retains the cap of two for a future
separately reviewed activation. Lambda concurrency, IAM and enabled flags were
not relaxed. All 16 focused regression checks passed, and the corrected source
passed Terraform validate in CloudShell.

A refreshed recovery plan proposed four creates, including an unexpected repeat
creation of the existing S3 bucket. That plan was rejected and never applied.
Eight live S3 control-plane reads independently confirmed the expected owner,
region, private/encrypted/ownership settings, exact TLS and paused-data policy,
CORS and absence of notifications. The retained 52-resource state was byte-for-byte
equal to its private backup.

A separate one-off plan used `-refresh=false` against that verified state. Its
JSON and textual review required exactly **three disabled mapping creates,
52 no-ops, no IAM changes, no updates and no deletes**. It also checked the exact
queue/function ARNs, unchanged ZIP/role, seven zero-concurrency functions,
private bucket controls, disabled API/signup and disabled schedules. Only that
reviewed saved binary was applied, returning exit 0 and three added resources.
No bucket recreation, import, state removal or pause-policy exception was used.

Recovery plan SHA-256:
`bc6ca030b89c227d6aa213c42878aa7ac87c5813d04e2e5841421d1f5fd2a227`

## Live AWS checks

The frozen [read-only audit](../scripts/verify_personal_paused_aws.py), fetched from
commit `54324f1` without changing the state-owning source checkout, passed 40/40
checks at `2026-10-23T13:29:56Z` (24 October in Melbourne). It checks:

- Exact account, source, original binary hash, real ZIP and 55 untainted state addresses.
- Lambda-only role trust, no attached policies, one scoped project runtime policy.
- All seven functions: `Active/Successful`, Python 3.12/x86_64, exact code hash and role, reserved concurrency zero.
- Exactly three disabled queue consumers without a scaling cap; both maintenance rules disabled.
- Disabled default API endpoint, explicit API/S3 CORS origins and methods, and admin-only Cognito signup.
- Four S3 public-access blocks, BucketOwnerEnforced, AES256, non-public policy, exact TLS/paused denials and no S3 notifications.

The audit only reads configuration and local metadata. It invokes no Lambda,
reads no application objects/messages and does not update Terraform state.
Lambda code acceptance and an Active status do not prove handler initialization
or execution on the managed AL2023 runtime.

A separate HEAD request to the paused API over HTTPS completed with certificate
verification enabled and returned 404. The live API readback confirmed protocol
`HTTP` and `DisableExecuteApiEndpoint=true`. The initial probe incorrectly
expected the REST API response 403; the expectation was corrected against
[AWS's documented HTTP API response](https://repost.aws/knowledge-center/api-gateway-disable-endpoint),
which is 404. This observation does not establish browser CORS, Cognito flows or
a working application endpoint.

## Live Google identity checks

After verifying the real AWS runtime role ARN and Lambda-only trust, the exact
previously reviewed GCP binary was rechecked against its SHA-256 and all 14
pre-apply checks, then applied successfully. Seven expected state addresses were
present without taint. Live reads confirmed an active pool/provider, the exact
AWS account/role condition and attribute mapping, the enabled invoker service
account, one `roles/iam.workloadIdentityUser` member and zero user-managed keys.

The sole allowed identity is the normalized assumed role
`arn:aws:sts::011154879765:assumed-role/ecoguard3184-personal-lambda`, using
`ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`.
No project-wide role, public invoker grant, compute service or static key was
created. The actual IAM readback completed at `2026-10-23T13:31:09Z`.
Short-lived token exchange from the Lambda role remains untested while runtime
execution is paused; the CloudShell/root caller is not that role.

## State custody and next deployment

Each cloud's persistent `~/ecoguard-c-personal-20261023/source` checkout owns its
personal root's `state/terraform.tfstate`. AWS stays at `2936764`; GCP stays at
`fdfaf23`. Plans, logs, selected reports and state backups remain in the root's
ignored `private/` directory. AWS retains initial/pre-recovery and final backups;
GCP retains its post-apply backup. Git does not transfer this state. Use one
operator and arrange private state custody before another teammate applies.

The existing paused S3 policy can interfere with bucket existence probing.
A future ordinary refresh must be inspected for false absence before any apply;
do not accept a repeat bucket create or discard the existing state. The one-off
`-refresh=false` recovery is not a general deployment recipe: it relies on the
specific backup and live checks above. Review current remote configuration before
any future plan. The first-plan gates intentionally reject this now-existing
managed state and must not be loosened to make a later plan pass.

Next work is a separately reviewed runtime increment: private inference hosting,
image publication, model loading, ingest/inference wiring, actual Lambda-role
federation, real media processing, browser authentication/CORS, Lex/notifications
and pause/restore acceptance. Continued funding must be checked for the intended
run period under the A$0 additional personal-spend limit. Paused storage and an
IAM-only deployment do not guarantee a zero future bill. The PR stays draft while
the separate SonarCloud gate and application acceptance remain outstanding.

Prepared with Codex assistance. The contributor should explain these controls
and the distinction between configuration checks and real processing at the demo.
