# Paused wiring repair: actual saved-plan review

Historical pre-apply review, recorded at 04:38 UTC. Its one permitted apply has
since completed; see the [actual paused deployment and independent verification](c-aws-wiring-deployed-paused-20261024.md).
The old review and its selected JSON remain historical evidence, not a new execution permission.

The new saved repair plan has passed independent read-only review against the actual 56-resource AWS checkpoint. It proposes **3 creates, 0 updates, 56 no-ops and 0 deletes**. No repair apply, application invocation, media upload or processing activation has occurred. The previous wiring apply failed once and its single-attempt authorization is consumed.

Account: `011154879765`; region: `us-east-1`; state-owning source: `3d2b3e7d64e43bfe0808f94ce06ed693be4ef268`. The current physical state remains serial72, SHA256 `ad411dc4f52a7f510cc19518ff9e60f25948999dccb8b8d363a6ed19da401f95`.

The saved binary is `c9c02a9b2c2c922c7bfa63c4ee373219ea128bca224a9299d3f51090c8575cd6`; its unchanged native JSON is `a1a89e36a95952b6c75940a110044efadce0bbf3be647aa5f224198d90c3105d`. The [selected actual evidence](../evidence/c-aws-wiring-repair-saved-plan-review-20261024.json) records the complete provenance and limits. Full plans, state and operational records remain private in the original CloudShell checkout.

## Proposed operation

Create only the restricted ECR repository policy, the Image-based `ecoguard3184-personal-ingest` Lambda, and its disabled SQS mapping. The policy omits the rejected `Resource` member; its attachment still scopes it to the sole project repository. Retain `lambda.amazonaws.com`, only `ecr:BatchGetImage` and `ecr:GetDownloadUrlForLayer`, exact source account and exact ingest function ARN. The runtime role's ingest log permission already completed in the failed operation; this plan requests no further runtime-role grant.

The proposed final pause configuration has eight functions at reserved concurrency0, four queue mappings disabled, both schedules disabled, API endpoint disabled, restricted signup, and S3 object access denied with no notifications. Existing images, source bindings, privacy controls and all 11 output descriptors remain as reviewed.

## Two explicit provider observations

The refreshed prior differs from the saved physical 56 export at two known fields, so full physical/prior equality is **false**:

1. The existing ingest log group's `tags` changes representation from present `null` to an empty map.
2. The runtime role's computed inline-policy mirror catches up with the already completed standalone policy. Its new string exactly equals that physical policy; the only parsed difference from its old mirror is the previously approved ingest log-stream ARN insertion.

Every other field of all 56 existing resources is unchanged. All 56 resource-change rows are known no-ops against the refreshed prior. These are provider read observations, not two additional proposed configuration updates or a new IAM grant. No generic normalization or edited plan document was used.

The first strict review remains blocked and unchanged. Independent audit1 also remains blocked: its checker incorrectly required a caller-identity row in `planned_values`. Actual physical/prior exports each contain the exact root identity; planned values and non-managed change rows contain none. Audit2 checks this exact profile, preserves both failures, and passed on the same native binary. Its summary SHA256 is `4966e322a1bc17ecb7bdf3becb1ee49e7ceed1ec840de0504ad41faeae58daa8`. Root observed it at 04:38:56 UTC. The summary file's 04:38:37 UTC mtime is local filesystem metadata, not an embedded signed event timestamp.

## Execution boundary

Execution requires a new specific action-time confirmation for this binary and a fresh eligible-credit/account check. Apply at most once; stop on failure. No retry, replan, broader policy, media upload, model request or activation is authorized by this review. Additional personal spending remains A$0; verified existing credits fund the permitted operation and do not create a hard account-wide spending cap.

The apply helper remains inert until actual plan, independent-review, fresh funding and new human-confirmation hashes are bound. It checks the current paused controls before the one apply, then validates all 56 existing values against the reviewed refreshed prior and the three new resources against their exact configured profiles, computed-field masks and SDK identities. Static review and seven focused offline guard checks passed; its main has not run.

A successful repair would establish a paused ingest deployment. Actual Lambda-role federation, automatic media processing and pause/restore evidence remain separate work. The account's observed Lambda concurrency limit is 10; future bounded activation needs its separately reviewed low-quota configuration and authorization.
