# Staged runtime controls: prepared implementation

This implementation defines the manual stage table from the 24 October design.
The staged 55-to-59 wiring has not yet been planned against AWS or applied. The
existing 55-resource foundation remains paused, and these source changes do not
modify its state. Committing or pushing this implementation does not deploy or
activate any stage.

The shared module's `runtime_controls=null` default preserves the old expressions:
the global switch still controls unreserved/zero Lambda concurrency, the API,
signup, S3 data deny, mappings, scaling blocks, maintenance rules and destinations.
`manage_upload_notifications=null` also retains the legacy `processing_ready`
resource count. Course auto tfvars, role trust, runtime permissions, package type,
timeouts, memory and the seven ZIP handlers are unchanged.

An explicit control object requires `runtime_enabled=false`. Missing function
reservations become zero, with known names and nonnegative integer reservations.
Enabled queue consumers require a reservation of at least two, matching their
mapping cap. Disabled controlled mappings have no `scaling_config`. Schedule and
API targets need positive reservations. These shared controls are independent;
the personal root exposes only the following fixed table, not individual switches.

| Stage | Reserved concurrency 1 | Private bucket data | Image/Run bindings |
| --- | --- | --- | --- |
| `foundation-paused` | none | denied | empty |
| `wiring-paused` | none | denied | required, retained |
| `auth-smoke` | API only | denied | required, retained |
| `media-manual` | API, ingest, infer, outbox, delete, cleanup | enabled | required, retained |

All profiles disable the default API endpoint, public registration, every queue
consumer, both schedules and upload destinations. Notifications remain unmanaged
and absent in these manual stages. If a later reviewed stage adopts that resource,
keep `manage_upload_notifications=true` when pausing and empty its destinations;
changing management back to false would destroy the resource. `processing_enabled`
continues to describe automatic ingest/infer processing, so it is false throughout
these manual profiles even when direct invocation is possible.

## Fixed inputs and boundaries

- The account, region, prefix, dedicated execution role and local backend are
  unchanged. The module remains one unconditional legacy-provider call.
- Every personal profile checks the real package's SHA-256 against
  `fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6`.
  A package change needs a separate source/package review.
- Non-foundation stages require exactly
  `011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:<64 lowercase hex>`.
  This syntax guard does not establish that a digest has been published or that
  it represents the reviewed amd64 image. No publication digest is filled in.
- The only accepted nonempty URL is
  `https://ecoguard-inference-adlnb7yumq-uc.a.run.app`; there is no trailing slash,
  path, query or independent audience input. The unchanged `CloudRunClient` uses
  that same `inference_url` as the Google token audience. The invoker is fixed to
  `ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com`.
  Reverify the actual Run identity/configuration before an authorized AWS plan.
- Seven functions stay Python 3.12/x86_64 ZIP functions. Only the eighth ingest
  function uses an Image package, with the existing ingest handler command.

## ECR retrieval policy in this independent variant

AWS documents a same-account repository policy granting `lambda.amazonaws.com`
only `ecr:BatchGetImage` and `ecr:GetDownloadUrlForLayer`; an execution-role grant
is an alternative. Lambda may try to add missing repository permissions if the
deployment caller can edit the policy. This draft does not rely on that fallback
and adds no ECR permissions to the application role. [AWS Lambda image permissions](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html#images-permissions)

This variant explicitly scopes the policy to the existing personal
repository plus the full ARN of `ecoguard3184-personal-ingest`. AWS's Lambda
cross-account retrieval example uses `aws:SourceArn`, and ECR recommends a full
source ARN to limit service access. Applying that exact-function condition to the
same-account policy is a design inference requiring separate review and actual
retrieval validation. The same-account example itself has no condition; the ECR
`SourceAccount` example is for CodeBuild, not proof that Lambda supplies that key.
Do not invent an additional runtime-role permission or broader account wildcard.
[Lambda retrieval example](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html#images-permissions), [ECR source conditions](https://docs.aws.amazon.com/AmazonECR/latest/userguide/cross-service-confused-deputy-prevention.html)

`ecr-pull-policy.tf` now implements that exact-function policy, including an
exact SourceAccount condition and Image Lambda dependency. Opt-in defaults false;
the personal root enables it only outside foundation-paused. The intended
increment is now four creates and 59 resources. The focused ECR/paused-profile
gate remains partial; the implementation includes a separate full increment gate,
also without apply authorization.
See [the independent policy review](ECR-PULL-POLICY-REVIEW.md) for limits and evidence.

## Offline checks

The predecessor draft's 15 shared and 12 personal resource-level mock plans **passed on 24 October
2026**, using Terraform 1.17.0 and the existing frozen AWS provider 6.67.0 in an
isolated test-only copy. Every run uses `mock_provider "aws"`,
`override_during=plan` and `command=plan`. No AWS credentials, IMDS, Lambda invoke,
image pull or cloud resource operation was used. Provider mocks still need the
matching provider binary for schema loading. [Terraform mock provider](https://developer.hashicorp.com/terraform/language/tests/mocking)

The predecessor ECR variant subsequently passed all 19 shared and 12 personal
mock-provider plans in root's native run, with actual provider-schema output.
Its earlier child IPC failure is retained alongside the successful parent logs.
Variant3 changed the controlled ingest mapping ARN to be plan-known while
retaining its configured-function dependency and added a target assertion.
Root then actually passed all four focused ECR mock plans in that fresh harness;
initialization and tests each exited zero without cloud credentials or calls.
After that successful run, only EOF/main-root formatting and evidence statements
changed; resource/test expressions remain unchanged.
The root-held task-workspace evidence, outside Git, is
`work/c-personal/aws-staged-increment-offline-evidence-20261024-3/root-focused-results.json`
and `root-focused-0.log`/`root-focused-1.log` in the same directory.
The full increment gate and preparer have 12 passing standard-library test
methods covering positive and negative synthetic inputs; they are not cloud
plans or live permission evidence.

Do not run the personal suite directly against the unmodified source. Its legacy
child module owns a separate real provider configuration, so the root mock does
not replace it. The original credential-free attempt failed safely before access;
later runs were skipped. The original shared attempt also failed because its
course lock lacked the host platform checksum. These two failed attempts are not
included in the 27 successful harness plans. Terraform documents test providers
as root configurations and legacy embedded providers as separate child
configurations. [Test providers](https://developer.hashicorp.com/terraform/language/tests#providers), [Legacy child providers](https://developer.hashicorp.com/terraform/language/modules/develop/providers#legacy-shared-modules-with-provider-configurations)

From the source checkout, prepare a **new directory outside the checkout**:

```sh
python3 scripts/prepare_aws_staged_mock_tests.py \
  --output /absolute/path/to/aws-staged-mock-tests
```

The standard-library script only copies an explicit public Terraform/test
allowlist. It never executes Terraform, installs software or accesses cloud
tools. It refuses existing output paths and source symlinks. Only in this test
copy, it removes the exact legacy child provider block and copies the personal
lock to the shared root to make the frozen platform checksum available. It keeps
all resources, variables, locals and test code byte-identical and writes a
`HARNESS-MANIFEST.json` with before/after hashes. No state, credential files,
provider cache or real Lambda ZIP is copied. The one public course
`deployment.auto.tfvars` is retained to match the tested inputs; unlisted local
configuration files are excluded. Do not use the test copy for
deployment or copy its provider/lock transformation back to production source.

Use only the already verified Terraform/provider artifacts and a filesystem-only
provider mirror with no direct download fallback. Keep provider data outside the
test source and disable credentials/IMDS. For example, on POSIX with those local
paths substituted:

```sh
export TF_CLI_CONFIG_FILE=/absolute/path/to/offline-terraform.rc
export CHECKPOINT_DISABLE=1
export AWS_EC2_METADATA_DISABLED=true
export AWS_SHARED_CREDENTIALS_FILE=/dev/null
export AWS_CONFIG_FILE=/dev/null
export TF_DATA_DIR=/absolute/path/to/fresh-shared-provider-data
terraform -chdir=/absolute/path/to/aws-staged-mock-tests/infra/aws \
  init -backend=false -lockfile=readonly -input=false
terraform -chdir=/absolute/path/to/aws-staged-mock-tests/infra/aws \
  test -filter=tests/runtime_controls.tftest.hcl
export TF_DATA_DIR=/absolute/path/to/fresh-personal-provider-data
terraform -chdir=/absolute/path/to/aws-staged-mock-tests/infra/aws/environments/personal \
  init -backend=false -lockfile=readonly -input=false
terraform -chdir=/absolute/path/to/aws-staged-mock-tests/infra/aws/environments/personal test \
  -filter=tests/stages.tftest.hcl \
  -var=lambda_zip=/absolute/path/to/the/unchanged/reviewed.zip
```

The shared suite contains 15 mock plans covering three legacy modes, independent
manual controls, retained notification management, selective automation and unsafe
inputs. The personal suite contains 12 mock plans covering all four profiles,
immutable image/URL guards, unknown stages and rejected package changes. The
shared `plan-only-package.txt` is opaque hash input for mock plans, never a Lambda
archive or deployable artifact. Personal positive cases require the reviewed ZIP.
The personal `hash-mismatch.zip` is a textual negative fixture: its existing
absolute `.zip` path passes the path check but its bytes must fail the pinned hash.
The existing first-plan Python fixtures remain historical regression tests only;
run them separately from the source `infra/aws` with
`python3 -m unittest discover -s tests -p test_personal_plan.py`. All 16 passed.
The whole AWS Python group had 25 passes and one unchanged missing-`botocore`
import error; no dependency was installed. Provider-free copies of the real
shared declarations/locals also passed 12 logic/input checks, which do not
substitute for resource mocks or actual service behavior.

## Remaining release blockers

1. The existing `check_plan.py` remains the historical first-create gate.
   The new `check_staged_increment_plan.py` enforces the exact existing-state
   wiring increment, and `scripts/prepare_aws_staged_increment.py` prepares at
   most one refreshed saved plan. The helper is inert by default and its actual
   state lineage/source/input pins remain pending; no actual plan has passed.
   See [the full increment review](STAGED-INCREMENT-REVIEW.md).
2. After the first wiring, return to `wiring-paused`, retaining both bindings and
   ingest resources. A stateless HCL variable cannot establish whether wiring was
   previously applied. Clearing inputs and selecting `foundation-paused` could
   destroy ingest resources; an existing-state stage gate must reject this.
3. The paused bucket's `ListBucket` denial can make provider `HeadBucket` refresh
   return 403. That is a planning block, never proof that the bucket is absent.
   Require its exact existing address/ID/owner/region and unchanged ownership,
   encryption, public blocks, CORS and TLS controls. Reject recreate/import/state
   removal/target changes. No reusable `-refresh=false` exception is introduced.
4. ECR publication/provenance, actual retrieval-policy behavior and a
   fresh real saved plan still need review. Mock plans do not validate service
   permissions, WIF, budgets, queue work or media behavior.
5. `auth-smoke` creates an owned QUERY task; it is not read-only and requires
   exact conditional cleanup. Manual media remains one serial owned fixture with
   all automation off. Outbox ignores an event limit and defaults to 100, so bound
   the real pending set first; account for the owned NOTIFY item without running
   notify. Finish owned cleanup while data access remains enabled, then return to
   wiring pause. A timeout is not evidence that Lambda or Run stopped executing.

No stage activation, new IAM policy, cloud plan/apply or complete two-cloud
acceptance is claimed by this draft.
