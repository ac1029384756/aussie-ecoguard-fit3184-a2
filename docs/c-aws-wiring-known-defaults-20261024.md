# Paused wiring defaults reviewed on 24 October 2026

The second real wiring plan returned Terraform exit 0 but its review stopped on an unknown `deletion_protection_enabled` field in the proposed ingest log group. No apply, IAM change, application request or state write occurred. AWS remains at 55 resources, serial 61. The rejected binary and review remain private and immutable; see the [selected evidence](../evidence/c-aws-wiring-known-defaults-20261024.json).

The source now declares log deletion protection=false, class=STANDARD and empty resource tags, matching the seven existing log groups. The ingest Image function explicitly uses its project Text log group and PassThrough tracing. Its disabled SQS mapping declares empty tags and a zero batching window. These settings do not permit an unknown logging, tracing or deletion-protection policy.

The full plan gate separately checks the optional/computed outputs observed in AWS provider 6.67.0. Only an exact explicitly named log can have an unknown empty name-prefix output; only the exact immutable Image function can have computed code checksums; only the exact disabled SQS mapping can have the reviewed inapplicable Kafka/stream outputs. Known stream defaults must match the existing typed empty lists/zeros. Individually named new-resource null/empty spellings are compared against the exact existing safe profile. No generic normalization or comparison bypass applies to the 55 retained resources. Future apply verification must check these actual output/default values and the resolved remote image digest.

All 59 AWS infrastructure tests passed locally in the existing locked amd64 application image with network disabled, the repository mounted read-only and two bounded temporary filesystems. Initial host/container environment failures remain retained: missing host botocore and missing writable test-temporary directories. The final run passed after correcting only that test isolation. Terraform formatting and the diff check passed; the change received independent static review.

This is a local source repair, not a deployment with 59 resources or an accepted new plan. A controlled source transition and a new real saved plan must precede any apply. The exact new ECR service retrieval and ingest-log permission grants still require a separate action-time confirmation. AWS processing remains paused.

Prepared with Codex assistance.
