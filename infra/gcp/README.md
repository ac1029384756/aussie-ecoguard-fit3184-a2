# GCP configuration and project boundaries

`deployment.auto.tfvars` belongs to the team's historical project
`ecoguard-fit3184-jlii0474`. Its AWS account, LabRole, Cognito IDs and bucket are
historical configuration, not evidence that the current operator can use them.
Keep its `identity_only=true` setting until a separate deployment is authorized.

The new project is `ecoguard-fit3184-a2-2026`, project number `995070689587`.
Use the [separate personal root](environments/personal/README.md) for its reviewed
setup: it has fixed project/AWS inputs, its own local backend and separate
first-plan/increment gates. Its seven identity resources have been applied after
verifying the actual AWS role. The current source additionally prepares explicit
registry and private-inference stages, neither deployed yet; its default retains
identity only. Do not use the generic example below against that existing state.

`ecoguard-fit3184-a2-2026.tfvars.json.example` is an explicit, non-auto-loading
generic starting point for IAM/WIF configuration. It deliberately leaves the AWS
identity unconfirmed and clears historical application settings. Creating a GCP
project does not authorize the team's AWS account or establish free compute.

Before planning, copy the example to a private JSON var-file outside Git. Verify
the intended AWS execution account and role with the resource owner, then replace
both placeholders. Verify the operation regions too. From the repository root:

```sh
python3 infra/gcp/check_identity_config.py \
  --var-file /absolute/path/to/approved-identity.tfvars.json \
  --expected-project ecoguard-fit3184-a2-2026 \
  --expected-aws-account VERIFIED_12_DIGIT_ACCOUNT \
  --expected-aws-role VERIFIED_EXECUTION_ROLE
```

The expected identities must come from independent account verification. The
checker rejects the unfilled example, omitted overrides, historical identities
that differ from the verified target, manifest drift and runtime activation.
It reads only local configuration. Passing does not verify cloud permissions,
billing, credits, Terraform ownership or deployment. Run the focused checks with:

```sh
python3 -m unittest discover -s infra/gcp/tests -v
```

Use a separate Terraform data directory and state for the new project. Pass the
approved file explicitly with `-var-file` to every plan; Terraform otherwise
loads the historical `deployment.auto.tfvars`. Never apply the new configuration
against the team's historical state. To manage the old project, obtain its
existing controlled state/backend or deliberately import its resources first.
This clone does not contain that state. A personal Google login does not migrate
any AWS resources or grant access to the old Google project.

Terraform also compares `manifest_sha256` with the exact bytes of
`config/model.locked.json`. Keep the immutable image, manifest and deployment hash
together when later preparing a runtime deployment. IAM/WIF-only configuration
does not create Cloud Run, a model bucket or an image registry. Enabling those
resources requires a separately verified, authorized funding and deployment plan.
