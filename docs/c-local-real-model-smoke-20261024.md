# Real local model smoke - 24 October 2026

Both locked models ran successfully in the already-built Linux amd64 inference
image, with networking disabled. On the public COCO two-cat sample, Grounding
DINO plus SigLIP2 returned **two cats**. Image and text embeddings had **768
dimensions**; both text vectors had unit norm, and the matching cat description
ranked above the unrelated car description. This is one execution smoke, not a
species-accuracy benchmark or cloud application acceptance.

The selected actual [JSON evidence](../evidence/c-local-real-model-smoke-20261024.json)
includes detections, scores, package versions, stage timings, hashes and measured
memory. All 15 files were downloaded from the manifest's pinned public revisions,
then checked against their exact lengths and SHA-256 hashes: **2,229,943,281 bytes**.
The weights and cache are outside Git. No token or remote model code was used.

The original COCO image endpoint failed certificate verification. The test used
the same public two-cat image from Hugging Face's documentation dataset instead;
its source, 694,498-byte size and actual SHA-256 are recorded. TLS verification
remained enabled. The model manifest and taxonomy were unchanged.

| Observed operation | Seconds |
| --- | ---: |
| Load detector from verified local cache | 5.196 |
| Load embedding model from verified local cache | 4.084 |
| Detect and classify the image | 40.488 |
| Embed the image | 0.447 |
| Embed each text | 0.105 / 0.104 |
| Complete container attempt including lifecycle | 52.944 |

The host's Docker engine is arm64 and ran the amd64 image through its configured
compatibility layer. These timings do not predict Cloud Run performance. The
kernel cgroup peak was **3,234,582,528 bytes (3.01 GiB)**; Linux process
`ru_maxrss` separately reported 2,792,882,176 bytes. Stage RSS and process
high-water values came from `/proc/self/status`, not an RSS-as-peak fallback.

The bounded container used four CPUs, 7 GiB memory with no swap, 256 PIDs,
UID/GID 10001, all capabilities dropped, no new privileges, a read-only root,
six read-only input mounts and one writable public-output directory. Docker
inspect and in-container UID/capability/cgroup observations verified those
settings. It exited zero, was not OOM-killed and was removed after its inspection
record was saved. No AWS/GCP credential directory or Docker socket was mounted.

The first attempt stopped before model loading because the smoke tool imported
`psutil`, which was only a development test dependency. That failed attempt and
its cleanup evidence were retained. The helper now reads Linux kernel memory
statistics without adding a release dependency; the successful second attempt
used the same immutable image and mounted the corrected helper read-only.

Cloud Run downloads into an in-memory filesystem. A read-only host cache does
not reproduce that allocation or network cold start. Cloud model downloads,
worker deadlines, authenticated warmup, Lambda-role federation, media processing,
pause/restore and broader accuracy still need actual verification. The current
AWS application remains paused and GCP still has identity resources only.

Prepared with Codex assistance. Keep the distinction between this local smoke
and cloud acceptance explicit in the report and demonstration.
