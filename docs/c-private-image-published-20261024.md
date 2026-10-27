# Private inference image published - 24 October 2026

The approved inference image was published to the private task registry and
verified at `2026-10-23T22:43:02.671410+00:00` (24 October Melbourne). The
publisher returned exit **0**, with status
`private-inference-image-published-and-verified`.

Immutable image URI:

`us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb`

The tag is `inference:c-20261024-1`. Actual remote manifest and config bytes
matched the reviewed archive exactly, including its compressed layer descriptors.
This is image-publication evidence. Cloud Run, real token exchange and cloud
inference remain unverified. Selected results are in the
[publication evidence](../evidence/c-private-image-published-20261024.json).

## Frozen provenance

| Item | Verified value |
| --- | --- |
| Archive | `inference-amd64-20261024-1.tar.gz`, 373,265,304 bytes |
| Uploaded archive hash check | `2026-10-23T22:23:34.261099+00:00` |
| Archive SHA-256 | `41ef8c5f4e1c0d0b9b6d3e8d1d814a0e7c5d1889082f1ab77882a122db6d94aa` |
| Remote OCI manifest | `sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb` |
| Remote image config | `sha256:3633f5354e5af61775e661925c9fc39ef96a243f1b23aa712e6fdd210c858643` |
| Validated OCI layout | 12 blobs, 14 files, 375,657,811 bytes |

The archive preserves the previously tested Linux amd64 image, without a model
cache or host credentials. This step did not rebuild or execute the image. The
uploaded size/SHA, extracted blob hashes, manifest/config chain and root filesystem
identity were checked before publication.

The [frozen publisher](../scripts/publish_personal_gcp_inference_oci.py) came from
`3d1cc6b454a7b623c6251c6b410733367fc66b48`, SHA-256
`831ec0ce94798ecf259f096b548c19836070cf0062be30a3ca04cdfc1110f8b2`.
It used Google's [crane v0.22.1 release](https://github.com/google/go-containerregistry/releases/tag/v0.22.1),
with the exact official asset/checksums and executable hashes retained in the
evidence. Normal TLS and the existing private gcloud credential helper were used;
no token or key was copied into this record.

## Failure recovery and verification

Two earlier Docker pushes failed on registry blob `HEAD` connections before
TLS/authentication, with zero successful layer lines. Their observations at
`2026-10-23T22:26:31.323618+00:00` and
`2026-10-23T22:31:46.668320+00:00` and all private evidence were retained.

The separately reviewed third attempt used the userland crane client and the
same approved archive, target and credentials. It issued one push command,
followed by registry and raw-byte readback. Its ordinary bounded HTTP retries
did not trigger another push command. No Docker daemon change, TLS exception,
new IAM/API access, container execution or Cloud Run deployment was used.

Final checks confirmed the state-owning source, saved plan, private IAM and prior
failure evidence remained unchanged. The GCP Terraform state stayed at nine
resources under source `00d58e0e8c65321cc759d575eafaba801c1e8253`. Registry image
publication adds no Terraform-managed resource. AWS retains its 55-resource paused
foundation; this operation activated neither cloud's application processing.

## Remaining boundary

The [registry deployment report](c-registry-deployed-20261024.md) remains a truthful
earlier snapshot of the empty repository. The next private-service increment
requires its own concrete saved-plan review using this actual digest; this
publication record does not claim a passing Cloud Run plan or runtime approval.
Authenticated warmup, cloud memory/deadline checks, Lambda-role federation and
real media processing are still separate acceptance work.

Additional personal spend remains **A$0**. Existing credits expire **28 October
2026**, with operator-reviewed cleanup by **27 October Melbourne** unless another
funded period is verified. Retained image storage can incur charges; no automatic
cleanup or guaranteed spending stop is claimed. No balance or billing identifier
is published.

Prepared with Codex assistance.
