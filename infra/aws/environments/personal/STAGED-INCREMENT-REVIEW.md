# Paused existing-state increment: prepared implementation

This implementation prepares review evidence for the paused 55-to-59 AWS wiring
increment. No actual AWS increment plan or apply has been performed. The existing
55-resource foundation remains paused; committing the implementation does not
change its state or activate processing. Earlier task-workspace drafts, patches,
mock harnesses and failure records remain preserved. The preparation helper does
not grant deployment permission and never invokes application code.

## Exact scope

The expected result is 59 resources: exactly four creates, eight updates and
47 no-ops. Every existing resource is preserved. No deletion, replacement,
import, address move, extra resource, deferred change or refresh drift is allowed.

| Existing address suffix under `module.ecoguard.` | Only permitted edit |
| --- | --- |
| `aws_lambda_function.zip["api"]` | Two inference environment values |
| `aws_lambda_function.zip["infer"]` | Two inference environment values |
| `aws_lambda_function.zip["delete"]` | Two inference environment values |
| `aws_lambda_function.zip["notify"]` | Two inference environment values |
| `aws_lambda_function.zip["outbox"]` | Two inference environment values |
| `aws_lambda_function.zip["cleanup"]` | Two inference environment values |
| `aws_lambda_function.zip["lex_fulfillment"]` | Two inference environment values |
| `aws_iam_role_policy.runtime[0]` | One ingest log-stream ARN in `ProjectFunctionLogs.Resource` |

Each ZIP's complete environment map must otherwise remain byte-for-value equal.
`ECO_INFERENCE_URL` changes from empty to
`https://ecoguard-inference-adlnb7yumq-uc.a.run.app` and
`ECO_GOOGLE_INVOKER_EMAIL` changes from empty to
`ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`.
The seven ZIP filenames and SHA-256
`fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6`
stay exact. Existing Lambda `last_modified` alone may be unknown, only when
after/planned are both null or omitted. A changed known timestamp, nested unknown
or unknown-plus-known contradiction is blocked. No other existing field is ignored.

The four additions are `aws_cloudwatch_log_group.functions["ingest"]`,
`aws_lambda_function.ingest[0]`, `aws_lambda_event_source_mapping.ingest[0]`
and `aws_ecr_repository_policy.lambda_ingest[0]`. The new function uses Image,
the immutable reviewed personal ECR digest, x86_64, 120 seconds, 2048 MiB,
1024 MiB ephemeral storage and only `ecoguard_aws.handlers.ingest`. Its full
remaining profile mirrors the existing API Lambda's safe defaults. The new log
profile mirrors the existing API log with only its name changed. The new mapping
mirrors the existing disabled inference SQS mapping, changing only its exact
queue/function targets. Its function ARN is constructed from the configured
Lambda name, retaining the resource dependency and remaining known during plan.
The null legacy branch is unchanged.

The [ECR policy review](ECR-PULL-POLICY-REVIEW.md) gives the sole service principal,
two pull actions, repository ARN and exact function/account conditions. No ECR
permission is added to the runtime role. Real Lambda retrieval with both source
conditions remains unverified and must never trigger a silent broader fallback.

All eight functions retain reserved concurrency zero; all four consumers remain
disabled without scaling blocks. The API endpoint, public signup, schedules and
upload notifications remain off, and the private bucket data-deny stays present.
This increment gate accepts only `wiring-paused`. Later authentication/media stages and
their return-to-pause gate are separate work. After wiring, pause means retaining
`wiring-paused`; selecting foundation with empty image/URL could delete the four
new resources and is rejected by this increment gate.

## Checkpoint and read-only preparation

The actual checkpoint reported by root is account `011154879765`, `us-east-1`,
owner source `29367645d62d47f16ac64659266dc3ba1540b89d`, raw-state SHA-256
`644e48c482187a7f782f65750059c8e84f084c68e5c400567c67c79fe4d4a26d`, serial 60.
The actual lineage is still pending. The preparer pins raw bytes/lineage/serial
and 55 untainted current instances, then exports that exact local state using
the restored frozen Terraform/provider with `show -json` without refresh.
The plan's refreshed prior must equal that export in full, including all 55
values. Raw Terraform attributes are not normalized into show values.

`scripts/prepare_aws_staged_increment.py` is inert without `--prepare`. Its
default output makes no tool or cloud call. Before enabling that flag, root
must freeze the controlled new source, exact input-record SHA, actual lineage,
restored official Linux tool/provider and all publication evidence. It checks
clean source, personal lock, default workspace and existing local backend;
it neither restores tools nor initializes/migrates state itself.

The exact input record is `reviewed-paused-aws-wiring-inputs-v1`; the helper
defines its required fields. It binds the unchanged original ZIP and public WIF
SHA `c8747dc930080ba76b9fede868e9a4fe0d3c165c779c6f7145913f9eb08b7815`,
the published ingest digest with raw remote-byte verification, verified private
Run URL/ready revision, and an explicit `RepositoryPolicyNotFoundException`
absence record for this one repository. `AccessDenied` never counts as absence.
Evidence paths/hashes must be reviewed, within the task folder and unchanged.
The historical course `config/google-wif.json` is not the reviewed personal
artifact; the seven retained ZIPs already contain the personal WIF file.

The helper creates a fresh private result directory, runs validation and exactly
one normal `plan -refresh=true`, saves its binary and JSON, lists unknown paths,
then runs the pure full increment gate. It never applies, retries, targets,
refresh-writes state or changes IAM/API settings. Any S3 HEAD 403 blocks the
attempt; there is no refresh=false, false-create, import or state-removal path.
Raw state, source and all pinned inputs are checked unchanged afterward.

## Offline evidence and remaining conditions

The predecessor variant's actual native provider schema and 19 shared plus
12 personal mock plans passed under root's credential-free environment with
Terraform 1.17.0/AWS 6.67.0. Its previous child IPC failure remains preserved.
The third draft has 12 passing standard-library test methods, including all
47 no-op values, all seven ZIPs, raw-state identity, false S3 creates, extra IAM,
new security unknowns, artifact/evidence scope and inert execution. Root also
actually passed its four focused ECR mock plans in the fresh harness,
including the plan-known mapping target assertion. Init/test exit codes were
both zero. No resource/test expression changed after those passing runs, so those results
remain applicable; no unchanged suite was rerun. These are local mock
checks, not a real AWS plan. The root-held task-workspace evidence, outside Git,
is `work/c-personal/aws-staged-increment-offline-evidence-20261024-3/root-focused-results.json`
plus `root-focused-0.log` and `root-focused-1.log` in the same directory. The
predecessor native schema/31 successes and original IPC failure remain under
`work/c-personal/aws-staged-ecr-policy-native-validation-20261024-1/`.

The actual provider schema marks `code_sha256` and `source_code_hash` as
Optional+Computed. New unknowns for them, log group class/name-prefix, whole
logging/tracing blocks or any other unreviewed setting remain blocked. Only
enumerated scalar output paths may be unknown with matching null/omitted after
and planned values. An actual plan with a new shape must be reviewed explicitly;
this implementation does not predict or waive that review.

No real AWS plan, published ECR digest, effective service pull, WIF exchange,
application/media processing or completed C acceptance is claimed. Plan evidence
requires the actual restored tools, missing pins and cloud read permissions.
Any later apply needs separate review of that exact saved plan and fresh live
policy/state/paused conditions; old foundation approval must not be reused.
