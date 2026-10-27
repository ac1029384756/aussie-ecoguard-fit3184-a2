# AWS ingest image: verified local export, 24 October 2026

The previously tested AWS ingest image was exported and its archive verified locally. This is a deployment artifact; no ECR publication, Lambda deployment or cloud video processing is claimed. AWS remains paused.

| Observation | Actual value |
| --- | --- |
| Local image/tag | `ecoguard-ingest:c-20261023-1` |
| Platform | `linux/amd64` |
| Local OCI manifest digest | `sha256:2fca6cdfe47846d8f7ce53723fcc0bf47750141290d8c1bcfe93c07795df3dc6` |
| Image config digest | `sha256:8963bf89ae167a13d8c6559783c0bbdb40be0a34e4993fea87757ce5148cdc58` |
| Archive | `aws-ingest-amd64-20261024-1.tar.gz`, 255,894,685 bytes |
| Archive SHA-256 | `c155ad79a993fefd878f9613e6fd1cf68d5b52a17d035b2fb425d59d564ae7d2` |
| Verified filesystem layers | 11 |
| Registry digest | Unknown; no registry request was made |

The export used only local Docker image inspection and save. The audit verified the sole OCI manifest/config, compressed blobs, expanded layer hash chain, and gzip round trip. All 19 application/domain/lock files matched current reviewed source bytes. FFmpeg/ffprobe executable files and installed RIC 4.2.2 dependency metadata were present. No model cache or host credential paths were found. It did not repeat the earlier container execution tests.

Docker reports the exact local reference `ecoguard-ingest@sha256:2fca…`. That local name does not establish an ECR upload. The retained [actual export evidence](../evidence/c-aws-ingest-export-20261024.json) records both distinct manifest/config digests and leaves `registryDigest` null. The image defaults to root, as previously built; no Lambda runtime user is inferred from that image setting.

The archive and checksum remain in the operator's local `outputs/` folder, outside Git. Before publication, recheck the archive checksum, correct AWS account `011154879765`, `us-east-1`, eligible credits and the existing project ECR repository. A separately reviewed wiring plan must preserve the seven existing ZIP functions and use this image only for the additional ingest function. The GCP inference image serves a different workload.

Prepared with Codex assistance. This report records an actual local export only.
