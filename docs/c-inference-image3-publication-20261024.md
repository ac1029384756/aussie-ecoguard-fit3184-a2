# Private IAM adapter image publication

The repaired image was privately published and verified at `2026-10-24T01:09:02.266079+00:00`. One explicit push returned zero. Registry readback verified the exact manifest, config and all ten compressed layers. The [selected evidence](../evidence/c-inference-image3-publication-20261024.json) binds the raw result and repository observations. Both earlier image tags remain intact.

Full and chunk uploads stalled before their files arrived. An 81,920-byte transport kit reused eight unchanged cloud-side blobs and supplied 48,783 literal bytes. Cloud reconstruction reproduced the complete original 373,265,221-byte gzip archive and SHA256 exactly, despite differing local/cloud zlib versions. Inputs, source and state remained unchanged. No altered export metadata or replacement digest was substituted.

During publication the deployed service remained image2 at serial 19 with 13 managed resources; full IAM and Run configuration were unchanged. This record proves publication of the [locally tested repair](c-inference-private-iam-adapter-image-20261024.md). A new reviewed image-only plan, successful apply and separate warmup result are still required. Prior failed HTTP evidence remains retained.
