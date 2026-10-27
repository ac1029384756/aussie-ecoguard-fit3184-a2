# Personal first saved-plan review - 24 October 2026

This is the **pre-apply snapshot**. The approved deployment subsequently ran,
with a three-mapping AWS recovery; see the [actual deployment and live checks](c-personal-foundation-deployed-20261024.md)
for the current outcome. The review below describes its original execution boundary.

Both plans below were generated in the authorized cloud-native shells from
source revision `fdfaf23b7d888c9579668d5c12c06ec649660191`. The real account/project
were independently rechecked immediately before planning. This record is a
review of proposed changes; **no apply or new IAM access has occurred**.

| Plan | Verified target | Creates | Changes | Deletes | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| AWS paused foundation | `011154879765 / us-east-1` | 55 | 0 | 0 | 28/28 passed |
| GCP identity only | `ecoguard-fit3184-a2-2026 / 995070689587` | 7 | 0 | 0 | 14/14 passed |

Each textual plan's resource headings matched its JSON changes exactly. Both
textual summaries confirmed the counts above, with no warning headers. Neither
plan imports resources, uses prior managed state or targets the historical course
stack. Full binary plans, JSON and state remain in ignored private directories;
only selected non-secret metadata is in the [review evidence](../evidence/c-first-cloud-plans-20261024.json).

## AWS foundation

The 55 creates comprise: one media bucket plus five privacy/ownership/encryption/
CORS/TLS controls; five DynamoDB tables; eight queues and one queue policy; seven
ZIP Lambdas and seven log groups; three disabled queue consumers; two disabled
maintenance rules and two targets; three scoped Lambda invoke permissions;
six HTTP API resources; one Cognito pool and one client; one empty ECR repository;
and one runtime role with one inline policy.

The new role is `arn:aws:iam::011154879765:role/ecoguard3184-personal-lambda`,
path `/`, trusted only by `lambda.amazonaws.com`. Every function references that
exact role. Its checked policy permits only project tables, bucket, work queues,
function logs and user email topics, plus regional `rekognition:DetectLabels`.
There is no IAM administration or account-wide project data grant.

The plan keeps every Lambda's reserved concurrency at zero, queue consumers and
maintenance rules disabled, the default API endpoint disabled, public signup
paused and S3 data access denied. S3 also has all four public-access blocks,
BucketOwnerEnforced, AES256 and an unconditional denial of insecure transport.
S3 and API CORS origins are the two explicit local development origins. The
bucket has `force_destroy=false`. There is no ingest image deployment, protected
inference endpoint or Lex configuration in this paused first plan.

The real CPython 3.12/Linux amd64 ZIP has 3,998 files, 72,766,834 bytes unpacked
and 33,286,409 bytes zipped. Locked-wheel installation, isolated offline imports
and native-library checks passed. CRC, strict new-project WIF and deterministic
repacking also passed. AWS AL2023/Lambda service execution is still unverified.

ZIP SHA-256:
`fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6`

Saved AWS plan SHA-256:
`997517ccfd38b8257d07ec1073843611c90bec29c9b6f00ff2a4c4ca863154ba`

## GCP identity scope

The seven creates are the invoker service account, workload identity pool,
AWS provider, one service-account IAM member and three API service records. The
APIs were enabled earlier; the records manage their enabled state and retain
`disable_on_destroy=false`. This plan creates no compute, registry, model bucket
or service-account key.

The sole grant is `roles/iam.workloadIdentityUser` on
`ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com` for the
`attribute.aws_role` principal set in this project's `ecoguard-aws` pool. Its
provider condition requires both AWS account `011154879765` and normalized role
`arn:aws:sts::011154879765:assumed-role/ecoguard3184-personal-lambda`.
No root-user principal, other AWS role, project-wide role or public invoker grant
is proposed. This permits short-lived identity exchange for that role, once the
resources exist; it does not prove a successful exchange.

Saved GCP plan SHA-256:
`4b7d995530d69be2da4edb8888e7592f75eaeedf89cf83455843c427ff7055a0`

## Execution boundary and remaining work

After action-time approval for the new IAM access, the execution order is AWS
first, verify the real runtime role ARN and private resources, then GCP trust.
Use only the exact reviewed saved plans and ZIP. Stop and obtain a new reviewed
plan if configuration, package, state or target identity changes. Do not pull a
new source revision into these state-owning checkouts during apply.

The private roots live under `~/ecoguard-c-personal-20261023/source` in their
respective cloud shells. Each root owns `state/terraform.tfstate`; its `private/`
folder contains the saved plan, gate output and review metadata. Keep one
operator and private state backups. Git shares source and evidence, not state.

Local validation passed with Terraform 1.17.0 and officially signed AWS 6.67.0 /
Google 7.46.1 providers. This batch's 49 offline checks passed: nine packaging,
25 AWS infrastructure and 15 GCP infrastructure checks. These are separate from
cloud mutation permissions, billing coverage and end-to-end acceptance.

The A$0 additional personal-spend constraint remains. The account allowances
were checked separately; a saved plan does not guarantee a bill. Runtime/image
publication, model warmup, real media processing, Cognito browser flows, Lex,
notifications, restoration and full assignment acceptance remain outstanding.
The remote SonarCloud gate is also still subject to its separate review; no rule
or gate has been suppressed. Keep the PR as a draft until review is complete.

Prepared with Codex assistance. Review and understand the resource boundaries
and evidence before the individual demonstration.
