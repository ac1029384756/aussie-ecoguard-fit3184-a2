# Personal registry saved-plan review - 24 October 2026

A real refreshed GCP saved plan passed **12/12 checks**: **two creates, seven
no-ops, no updates/deletes, no drift or warnings**. Preparation exited zero and
the existing raw state remained byte-for-byte unchanged. Nothing in this review
has been applied or uploaded. The selected [JSON evidence](../evidence/c-registry-saved-plan-review-20261024.json)
contains the observed plan and archive metadata, not full plans, state or balances.

| Target | Proposed action |
| --- | --- |
| `ecoguard-fit3184-a2-2026 / 995070689587` | Retain existing seven identity resources |
| `artifactregistry.googleapis.com` | Enable and manage this API |
| `us-central1/ecoguard` | Create an initially empty standard Docker repository |

Source: `00d58e0e8c65321cc759d575eafaba801c1e8253`.
Saved binary SHA-256:
`0f62543fe74a7b0fc71e9e8c2b1930de853448d1ab4c257b9d215399c9d5ba86`.
The observed preparation completed at `2026-10-23T22:08:10Z`, 24 October Melbourne.

The [frozen helper](../scripts/prepare_personal_gcp_registry_plan.py), fetched from
`5dd4ec3` and hash-checked without first changing the state owner's checkout,
verified the original seven-resource backup, operator/project, provider and local
backend. It moved only the controlled GCP source checkout to `00d58e0`, restored
the same official Terraform 1.17.0 archive after Cloud Shell's temporary VM reset,
initialized with the readonly Google 7.46.1 lock, and validated the configuration
before normal refreshed planning. It performs no apply, service enablement or IAM
command. The authoritative state remains the existing GCP CloudShell personal
backend; the last applied identity source was `fdfaf23`.

Full binary/JSON/text plans, logs and checkpoint backup are retained privately in
that root's `private/registry-plan-20261024-1/`. Do not regenerate the plan while
claiming approval for this hash, use an empty backend, or reuse the first-plan
gate. The AWS state-owning checkout and paused application were untouched.

## Automatic access and live checks

Google documents that the first repository creates
`service-995070689587@gcp-sa-artifactregistry.iam.gserviceaccount.com` and grants
`roles/artifactregistry.serviceAgent` on this project. This Google-managed IAM
effect is additional to the two Terraform-managed resource entries and must be
included explicitly in execution approval. No manual service-agent role grant
is needed. See the [official service-agent description](https://docs.cloud.google.com/artifact-registry/docs/ar-service-account).

Fresh project and organization IAM reads found zero `allUsers` or
`allAuthenticatedUsers` bindings. Artifact Registry and both scanning APIs were
disabled; the expected service-agent role was absent. The repository plan has
the exact project, region, `DOCKER` format and `STANDARD_REPOSITORY` mode, with no
remote/virtual repository or external KMS key. The project's billing link was
independently matched to the account inspected in the UI. These live reads were
configuration-only and their private policy snapshots were retained.

An approved apply must recheck the operator, source, provider, unchanged state
and exact binary hash immediately before execution. Afterward, verify nine
managed resources, repository/API settings and IAM inheritance; require the
project IAM delta to contain only the expected service-agent access and retain
the original WIF/service-account policies and zero user-managed keys. Preserve
the post-apply state even if the apply or subsequent verification fails.

## Exact image prepared for a later approved publication

The previously tested inference image was exported, not rebuilt. The local
Docker store identifies its OCI manifest as
`sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb`;
its distinct config digest is
`sha256:3633f5354e5af61775e661925c9fc39ef96a243f1b23aa712e6fdd210c858643`.
The archive preserves tag `ecoguard-inference:c-20261023-3`.

File: `inference-amd64-20261024-1.tar.gz`, **373,265,304 bytes**.
Archive SHA-256:
`41ef8c5f4e1c0d0b9b6d3e8d1d814a0e7c5d1889082f1ab77882a122db6d94aa`.

Independent streaming review verified all manifest/config/layer hashes and ten
RootFS diffIDs. It checked 39,560 paths and matched 20 application/config/lock
files against the source. No downloaded model cache or host credential paths
were found. The expanded layer TARs total 1,310,668,800 bytes; reserve at least
3 GiB for Docker loading, plus space for the uploaded archive.

Classic Docker may expose the config digest as its image ID. Verify the preserved
tag, actual config digest, ten RootFS layers, Linux amd64 platform, UID and startup
configuration after loading; do not confuse that with the local store's manifest
ID. Read the actual registry manifest digest after a successful push before
constructing any private-inference plan. No registry digest exists in this review.

The proposed transfer destination is this project's Google Cloud Shell, followed
by its private `us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference`
path. Publishing requires explicit coverage of this exact archive and destination.
Do not export a credential, create a service-account key or run the image merely
to publish it. Cloud Run, its runtime account/invoker grant and AWS activation
are separate later increments.

## Funding boundary

The pre-existing credit was reverified and expires **28 October 2026**. The
additional personal-spend limit remains **A$0**. Retain only this single image for
the bounded test period, with operator-reviewed cleanup by **27 October Melbourne**
unless a new funded period is verified. No cleanup automation or account-wide
spending stop has been created.

Registry storage has an account-aggregated free allowance; do not infer unused
allowance from this project's image size. Even charging the roughly 0.35 GiB
image at the full listed storage rate for four days is under US$0.01, before
existing credit. Inbound transfer is free; this batch enables no scanning and
starts no inference compute. See [current registry pricing](https://cloud.google.com/artifact-registry/pricing).
The paid account's retained trial credit covers eligible usage until expiration;
it does not guarantee zero charges afterward or for unrelated account usage.
See the [official credit and Free Tier rules](https://docs.cloud.google.com/free/docs/free-cloud-features).

Prepared with Codex assistance. Plan review and local artifact verification do
not establish runtime deployment or full assignment acceptance.
