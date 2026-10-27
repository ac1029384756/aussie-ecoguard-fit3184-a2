# Independent ECR pull policy variant, 24 October 2026

This prepared implementation defines the ECR retrieval policy for the paused
wiring increment. The existing personal AWS foundation remains paused at 55
resources. No actual AWS wiring plan, apply, policy change or application
invocation is claimed here; preparing or committing source does not deploy it.
The earlier task-workspace variants, harnesses, failure records and patch SHA
`63df7220402169077264afe3434895d6bb3401294420027cf34090719678eba6`
remain preserved. This implementation does not authorize deployment.

## Exact policy and dependency

The optional `manage_ingest_ecr_pull_policy=false` default preserves historical
module behavior. The personal root enables it only for a non-foundation stage;
the resource additionally requires `local.has_worker`. It therefore creates no
policy for the current foundation and retains it when returning to wiring-paused.
The policy has one Allow statement, no wildcard and no extra principals/actions:

- Principal: `lambda.amazonaws.com`.
- Actions: `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`.
- Resource: `arn:aws:ecr:us-east-1:011154879765:repository/ecoguard3184-personal-worker`.
- `ArnEquals` `aws:SourceArn`: `arn:aws:lambda:us-east-1:011154879765:function:ecoguard3184-personal-ingest`.
- `StringEquals` `aws:SourceAccount`: `011154879765`.

The ingest Lambda explicitly waits for the repository policy. Its source ARN is
constructed from the reviewed function name/account/region; it never references
the Lambda resource, so it creates no dependency cycle. A resource precondition
rejects any other account, region, prefix or worker repository/image URI. No ECR
permission is added to the execution role. The runtime role still gains only the
ingest log stream already required by the original staged design.

## Official sources and what they establish

AWS's [Lambda image permission documentation](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html#images-permissions)
specifies the Lambda service principal and these two pull actions. It also says
Lambda may automatically add missing repository permissions if the deployment
caller has GetRepositoryPolicy and SetRepositoryPolicy. This variant explicitly
manages the policy and does not rely on automatic repair or grant extra role
permissions. The caller's administrative rights are separate from the Lambda
execution role; no caller policy is created here.

AWS's [ECR service policy example](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-policy-examples.html)
uses SourceArn and SourceAccount to scope service access. That example is for
CodeBuild. The Lambda retrieval example documents SourceArn for Lambda; using
both exact conditions for this same-account Lambda is a conservative design
inference, not a live retrieval result. [IAM global condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-sourcearn)
explain that these keys depend on service request context; SourceAccount is
redundant when the source ARN includes the account. [IAM condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html)
explain that an absent key does not match a positive condition. No IfExists,
wildcard ARN, alternate role permission or broad fallback is included.

## Offline evidence and remaining release blockers

The focused `check_ecr_policy_plan.py` expects 55 prior and 59 planned managed
resources: exactly four creates (ingest log, Image function, disabled mapping,
repository policy), eight updates and 47 no-ops. It rejects extra actions,
deletion/replacement/import/drift, any policy expansion, nonzero reservation,
active pollers/signup/API/schedules, removed bucket pause/privacy boundaries,
changed ZIP bytes/path, and runtime-role changes beyond one ingest log ARN.
The focused gate still reports `fullIncrementGatePassed=false`; it cannot be
used alone. This variant adds `check_staged_increment_plan.py`, which
compares all 55 physical values with the refreshed prior and permits only the
reviewed eight updates/four additions. It reports an offline gate result, never
cloud verification or apply authorization. See [the full increment review](STAGED-INCREMENT-REVIEW.md).

The predecessor ECR variant's 19 shared and 12 personal mock plans actually
passed under root's credential-free native run using Terraform 1.17.0 and AWS
provider 6.67.0. The earlier child-process IPC failure remains preserved beside
the successful parent logs; it was not a provider compatibility failure. Those
31 results are historical evidence for the predecessor, not a real AWS plan.
Variant3's fresh isolated harness also actually passed all four focused ECR
plans under root's credential-free native run, including the exact, plan-known
ingest-mapping target assertion. Initialization and tests both exited zero.
After those passing runs, only EOF/main-root formatting and evidence statements
changed; no resource or test expression changed.
The new full-gate/preparer fixtures pass with only the Python standard library.
The root-held task-workspace records, outside Git, are
`work/c-personal/aws-staged-increment-offline-evidence-20261024-3/root-focused-results.json`,
`root-focused-0.log` and `root-focused-1.log` in the same directory. The earlier
31 native results and original IPC failure remain in
`work/c-personal/aws-staged-ecr-policy-native-validation-20261024-1/`.

Before an actual plan, bind the raw state SHA, lineage/serial, official restored
tools, controlled source revision, original ZIP and reviewed personal WIF,
published image/Run proof and a live record that no untracked ECR policy exists.
A Terraform policy create can replace an existing untracked policy; an access
error is not absence. Resolve any S3 HEAD 403 as a blocked refresh diagnosis;
never use blanket refresh=false, imports, state removal or presume a new bucket.

After a separately authorized paused wiring deployment, verify the full returned
ECR policy is still exactly this statement (including after Lambda creation),
then verify real image optimization/retrieval without invoking application code.
If AWS omits either source context key or auto-adds a broad permission, retain
the paused state and stop for evidence review. Do not silently broaden policy.
Publishing the ingest ECR image, any AWS cloud plan/apply, stage activation and
application/media/WIF tests remain outstanding.
