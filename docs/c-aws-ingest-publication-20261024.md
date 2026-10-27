# Private AWS ingest image publication

The ingest image was published to the existing immutable private ECR repository at `2026-10-24T00:51:57.487305+00:00`. One explicit push returned zero. Registry readback verified the original manifest, separate config and all eleven compressed layer bytes; the [selected evidence](../evidence/c-aws-ingest-publication-20261024.json) binds the private raw records.

Before and after publication, all 40 paused checks passed. The physical state remained 55 managed resources at serial 60. No function ran, no policy or IAM grant changed and no credentials were saved by this publisher. Registry storage can consume existing credits.

The earlier attempt stopped before creating a result directory or push marker. Its version-comparison diagnosis is retained. The new publisher uses the same credentialed API environment, canonicalizes only the local version check and places large temporary files in an exclusive `/tmp` directory. Original archives remain intact.

This proves image publication. Lambda deployment, role federation and image/video processing still require actual acceptance results. The archive build commit remains unknown; nineteen installed source payloads are separately bound to the publication transaction source revision.
