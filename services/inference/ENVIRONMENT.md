# Inference service deployment contract

The same service supports private Cloud Run IAM or an Oracle-hosted deployment.
Choose the explicit production authentication mode for the actual host.

Run Python 3.12. The Docker build context is the repository root. The standard-library
helper prints a `linux/amd64` command, including on Apple Silicon Macs:

```sh
python3 scripts/build_containers.py inference --image ecoguard-inference:20261023-1 --dry-run
```

Use `python` instead of `python3` on Windows. The helper prints PowerShell syntax on
Windows and POSIX shell syntax on macOS/Linux; it resolves the build context from
the script location, so it also works outside the repository root. Omit `--dry-run`
for the same print-only behavior. An explicit non-`latest` image tag is required.
Only add `--build` after reviewing the command and selecting the intended Docker
engine/builder. This checks for a running Linux engine and Buildx, then builds and
loads the image without pushing it or starting a container. Building may download
base images and dependencies; Apple Silicon needs working amd64 emulation in Docker.
For a release, add `--base-image` with a reviewed official Python 3.12 slim digest.
Replace the digest placeholder before running this print-only example:

```sh
python3 scripts/build_containers.py inference --image ecoguard-inference:20261023-1 --base-image 'python:3.12-slim@sha256:REPLACE_WITH_VERIFIED_64_HEX_DIGEST' --dry-run
```

The helper passes `BASE_IMAGE` to the Dockerfile and accepts only
`python:3.12-slim@sha256:<64 hex characters>` or
`python:3.12-slim-bookworm@sha256:<64 hex characters>`. Tags alone are rejected
when this option is supplied. Omitting it retains the Dockerfile's development
default; the helper does not resolve or verify a digest or the final image/model
runtime. Follow the existing deployment and model acceptance gates.

The same helper's AWS ingest target separately requires the explicit committed
RIC version `--aws-lambda-ric-version 4.2.2`; its hash lock and installation gates
are documented in [AWS container build preparation](../aws/ENVIRONMENT.md#container-build-preparation).

Keep the PyTorch CPU extra index in `requirements.lock.txt`, immediately after
its PyPI `--index-url`. pip resets the command-line index list when it reads a
requirements-file `--index-url`, so a Docker command-line extra index alone
cannot resolve the locked `torch==2.14.1+cpu`. Preserve both index directives
when regenerating the lock; the current uv generation header records the
original command, which omitted the extra index. No package versions changed
in this repair. See the [local build record](../../docs/c-local-build-20261023.md)
for the actual validation scope.

Deploy Cloud Run with 4 vCPU, 8 GiB, request concurrency 1, minimum instances 0,
maximum instances 1 and a 360-second request timeout. These are unbenchmarked
starting limits. Use `/health` for startup/liveness and `/ready` for model
readiness. `/ready` is 503 until both real models have loaded; it does not
download weights. `/healthz` and `/readyz` remain compatibility aliases for
existing local/Oracle callers. For Cloud Run, use the paths without a final `z`:
Google documents reserved paths ending in `z` that may be intercepted before
the application. [Cloud Run reserved URL paths](https://docs.cloud.google.com/run/docs/known-issues#reserved-url-paths).
Cloud Run IAM still protects both probe aliases at the service boundary. An authenticated
`POST /v1/warmup` can load and verify them before a demo. IAM must reject
unauthenticated callers; only the dedicated WIF impersonated invoker service
account receives `roles/run.invoker`. Never grant `allUsers` or
`allAuthenticatedUsers`. Do not disable Cloud Run's invoker IAM check.

## Environment

| Variable | Required value |
| --- | --- |
| `SERVICE_AUTH_MODE` | `cloud-run` for Cloud Run; **`oracle` for Oracle**. Docker defaults to Cloud Run, so Oracle must override it. |
| `K_SERVICE` | Supplied by Cloud Run. Do not forge it. It grants no platform trust in Oracle mode. |
| `SERVICE_TOKEN_AUDIENCE` | Required in Oracle mode: the exact configured audience of the Google service-account ID token, normally the public HTTPS service URL. |
| `SERVICE_TOKEN_EMAIL` | Required in Oracle mode: the exact dedicated `invoker@project.iam.gserviceaccount.com` identity permitted to call this service. No wildcard or domain-wide allowance. |
| `COGNITO_ISSUER` | `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>` |
| `COGNITO_CLIENT_ID` | Exact browser Cognito app client ID. Access tokens only. |
| `SOURCE_S3_HOSTS` | Comma-separated **exact** bucket hosts, e.g. `a2-media.s3.us-east-1.amazonaws.com,a2-query.s3.us-east-1.amazonaws.com`. No wildcard. |
| `SOURCE_KEY_PREFIXES` | Defaults to `derived/,queries/`. Only server-generated frame locations belong here. |
| `MODEL_MANIFEST_PATH` | Local path to the locked manifest, e.g. `/config/model.locked.json`. |
| `MODEL_MANIFEST_SHA256` | SHA-256 of the exact manifest bytes. Mandatory for inference. |
| `TAXONOMY_PATH` | Local taxonomy path, default `/config/taxonomy.json` in Docker. |
| `MODEL_CACHE_DIR` | Verified model artifacts only, default `/tmp/ecoguard-models`. Model cache memory must fit within Cloud Run memory. |
| `INFERENCE_TIMEOUT_SECONDS` | Default 240, less than the Cloud Run request timeout. |
| `TORCH_THREADS` | Default 4. |

For local integration only, use `SERVICE_AUTH_MODE=local` and a random
`LOCAL_SERVICE_TOKEN` of at least 32 characters, sent as Bearer in
`X-Serverless-Authorization`. Local mode refuses to start authenticating when
`K_SERVICE` is present. It still verifies real Cognito JWTs. Never commit that
local secret. There is no default bypass or mock inference mode.

`SERVICE_AUTH_MODE=cloud-run` is a trusted adapter for a **private Cloud Run IAM
endpoint only**. Require platform IAM authentication (`invoker_iam_disabled=false`),
retain the exact reviewed service invoker policy with no `allUsers` or
`allAuthenticatedUsers`, and expose no path to the container that bypasses IAM.
`K_SERVICE` must be present; it selects the platform adapter and is not identity
proof by itself. Cloud Run validates the Google ID token and invoker permission
before the request reaches this adapter. The platform can consume or modify
`X-Serverless-Authorization`, so the app does not require its forwarded presence
or pretend to reverify a stripped token. A fabricated bearer header was never an
independent authentication check. Check the actual private IAM configuration as
part of deployment verification; this adapter is not for a public raw container.
See Google's [service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
and [header handling](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent) documentation.

The `Authorization` header on `/v1/query-authorizations` still carries the independent
Cognito access token. The app checks its RSA signature, fixed issuer, client_id,
token_use, expiry, issued-at and subject using Cognito JWKS. This path never
initializes torch or downloads model weights and has an 8-second deadline.

## Oracle production authentication

Oracle has no Cloud Run IAM proxy. Configure `SERVICE_AUTH_MODE=oracle`,
`SERVICE_TOKEN_AUDIENCE` and `SERVICE_TOKEN_EMAIL`; omit `LOCAL_SERVICE_TOKEN`.
Serve the application behind an HTTPS reverse proxy and keep the raw application
port private. Forward the original `X-Serverless-Authorization` and
`Authorization` headers without logging their values. The former contains the
**complete signed Google ID token**, including its signature. A stripped Cloud
Run token, a Google access token, a mere header, an injected `K_SERVICE` value or
the local integration secret cannot authorize an Oracle request.

AWS retains the WIF short-lived identity path, then calls
[generateIdToken](https://docs.cloud.google.com/iam/docs/create-short-lived-credentials-direct)
for the dedicated invoker service account with `audience` equal to
`SERVICE_TOKEN_AUDIENCE` and **`includeEmail: true`**. Oracle verifies the RSA
signature using the fixed Google OAuth JWKS endpoint
`https://www.googleapis.com/oauth2/v3/certs`. It requires RS256, issuer
`https://accounts.google.com` or `accounts.google.com`, the exact single audience,
valid expiry/issued-at/subject, the exact configured email and Boolean
`email_verified: true`. JWKS refreshes use a shared single-flight cache, bounded
HTTPS reads and an eight-second verification deadline. Expired cached keys are
not accepted if refresh fails. Token headers never select the JWKS URL.

`/v1/query-authorizations` verifies both the Google service token and the original
Cognito access token within one eight-second budget. The model endpoints verify
only the trusted service identity and use the existing service-generated job
context. This does not change model manifests, frame contracts or temporary-file
cleanup. Google IAM/WIF setup and Oracle TLS/process deployment are managed
separately; offline signature fixtures do not prove that live federation works.

## Requests and media handling

`POST /v1/infer`: `{jobId, ownerSub, generation, manifestVersion, mediaType,
frames:[{frameId,timestampSeconds,url,sha256,entryLabels,entryModelVersion?}],
deadlineAt?}`. `generation >= 1`, `mediaType` is `image` or `video`, and `sha256`
is mandatory. `entryLabels` is the original Rekognition Labels array, including
Instances and BoundingBox fields. `schemaVersion` may be omitted or `"1"`.
For images send one frame at zero; videos use 0,10,... seconds, at most 12 frames.
The URL TTL should be at least 900 seconds. URLs must use HTTPS, approved bucket
hosts and key prefixes; no redirects, userinfo, fragments or non-443 ports.
Every downloaded frame is verified against the supplied checksum before decode.

Response: `{schemaVersion:"1",jobId,manifestVersion,counts,tags,frames,features,
classification,featureVersion,truncatedFeatures}`. Frame counts are aggregated
using per-species maxima, never sums across time. `features` holds up to 32 pet
crop embeddings with `species,vector,featureVersion,frameId,bbox`. The
`truncatedFeatures` flag explicitly reports the cap. Boxes use normalized
`x,y,width,height`. Full counts are not silently truncated. A frame exceeding
64 detections fails with an explicit error.

`POST /v1/embed`: `{jobId,manifestVersion,text,deadlineAt?}` returns a real
normalized text vector, `featureVersion`, `manifestVersion` and `schemaVersion`.
Only compare vectors with an identical featureVersion, which includes the exact
model revision and preprocessing version.

`POST /v1/query-authorizations`: `{requestId,purpose:"file"|"pet"}` returns
`{sub,requestId}`. AWS must compare this subject with the original authenticated
subject before creating a query. No client-supplied owner field is accepted here.

The trusted worker service is responsible for authorizing media ownership and
generating the task context. A Cognito token is not retained in queues or media
metadata. Cloud Run never writes ordinary media to object storage. Downloads and
decoded crops are request-scoped; the parent process owns the temporary folder
and kills the model subprocess before cleanup on deadline or cancellation.
Only verified model files persist. A retry starts a fresh model process after a
timeout. Response and request bodies are capped; validation errors omit input
values, signed URLs and tokens. Access logging is disabled in the container.

## Model locking, validation and limitations

The example manifest deliberately fails closed. `tools/lock_manifest.py` pins
official model revisions, reads LFS weight SHA-256 metadata without downloading
weights and hashes small configuration/tokenizer files. Inspect its output size
estimate before a real warmup. `MODEL_MANIFEST_SHA256` locks the complete config;
all downloaded artifacts are byte-length and SHA-256 verified and models load
offline using safetensors with `trust_remote_code=False`.

Use GCS `gs://bucket/path` artifact URLs for deployment after uploading the exact
verified files. Grant the runtime service account read-only access to that model
prefix. Changing artifact locations changes the manifest digest. To upgrade a
compatible model, publish a new immutable manifestVersion and its hash, deploy
a new revision and warm it up, then route new jobs to it. In-flight jobs retain
their original manifestVersion. Rebuild the feature index when featureVersion
changes. An incompatible model architecture needs a new adapter.

The actual adapters are Grounding DINO Tiny and SigLIP2 Base (official selected
model cards declare Apache-2.0). They have **not passed the assignment's species,
counting or individual-pet retrieval benchmark**. Generic pig/toad labels are
not promoted to feral pig/cane toad. Similarity scores are candidate ranking,
not identity confirmation. Local contract/security tests and a single model
smoke must not be described as model acceptance.

## Current v3 model and bounded semantic evidence (2026-10-08)

The current locked manifest is `config/model.locked.json`, version
`ecoguard-models-2026-10-08-v3`, SHA-256
`639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae`.
Its feature identity is
`siglip2-base-256-animal-crop-v3:3f9f96cb90da5dbc758b01813f2f6f1aee24c1ab:rgb-exif-animal-crop-text64-lowercase-v3`.
The model artifact bytes and revisions remain unchanged. DINO now proposes
locations from the fixed prompts; a shared SigLIP2 crop class bank chooses the
species, including explicit non-animal rejection classes. Independent DINO
prompt scores are no longer treated as comparable species probabilities.
Text is explicitly lowercased before fixed 64-token preprocessing, because the
pinned tokenizer does not apply that training convention itself. Detection
provenance may now be `grounding-dino+siglip2`.

The immutable `retrievalCalibration` holds separate monotonic image and text
score transforms, each requiring at least 0.5. Combined retrieval requires both
modalities to pass for the same crop and ranks by their geometric mean. The
40 calibration pairs describe breed/species relevance, not individual identity.
Reproduce the parameters offline without models, pictures or vectors:

```powershell
python scripts/fit_pet_calibration.py --check
```

The check requires exact data equality with the manifest. Its committed inputs
are the sanitized pair summaries and provenance in `config/calibration/`.
The backend ships the same policy and selects it only for the exact feature
version. Missing/mismatched v3 policy fails closed. Archived v2 is retained at
`config/manifests/ecoguard-models-2026-10-07-v2.json`; old queued work needs a
separately configured v2 service. A v3 service rejects a v2 manifest request.
Existing v2 features must be reindexed before comparison with v3; there is no
silent vector conversion or automatic historical reindex.

The sanitized result is [model-quality-v3-20261008.json](evidence/model-quality-v3-20261008.json).
Four gallery sources and four calibration sources were separated from eight
previously unseen Oxford test photos before scores were computed. All eight
held-out photos produced the labeled cat/dog species and a pet feature. The
production Worker retrieved the labeled breed at rank 1 in 7/8 photo queries
and 7/8 combined queries. One bulldog remains a miss at the frozen threshold;
it was not removed from the denominator. The initial four positive text queries
replayed calibration prompts, so their 4/4 result is not independent text
holdout evidence. A separately frozen supplementary set of four new phrasings
scored 4/4, with 0/4 unrelated-text false positives; combined rephrasing stayed
at 7/8. These small semantic checks do not verify pet identity, all invasive
species, diverse scenes or production accuracy.

The final model runs used cached real weights and a local SHA-checked image
transport with an empty Rekognition fixture. They do not establish the mandatory
live AWS entry-model chain or Oracle deployment. The inference suite passed
72 cases, including 13 new model-policy cases. Original failures and raw assets
remain under ignored `tmp/a04-model-quality-20261008/`; images and vectors are
not committed. The current maximum-video timing is a separate core acceptance
check and must not be inferred from these single-image timings.

## Historical local evidence on 2026-10-07

`evidence/local-smoke-v2-20261007.json` records a real CPU run using the pinned
weights, with the two-cat sample linked from
[Hugging Face documentation](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/coco_sample.png).
The image is kept only in ignored local temporary storage; its checksum is in
the evidence. The model artifacts total 2,229,943,281 bytes and were downloaded
to the ignored `D:\3184a2\models` cache, never the repository or a cloud bucket.
The earlier manifest's note describes the metadata-only locking step, before
that later weight download.

The original multi-label prompt produced a wrong fox label and inaccurate boxes.
That failed observation is preserved in `evidence/local-smoke-20261007.json` and
`evidence/model-baseline-v1.json`. The v2 adapter uses one canonical prompt per
species followed by suppression of overlapping predictions. After correcting
SigLIP2 padding to the model's 64-token limit, the v2 smoke returned exactly two
cats and 768-dimensional normalized vectors. Image/text cosine was 0.15585 for
the cat description and -0.08067 for the car description. This is not an
individual-pet accuracy result.

Four-thread local detection took 17.375 seconds per frame; cached model loading
took approximately 6.16 seconds. Peak process working set was approximately
1.87 GiB; Cloud Run additionally counts the roughly 2.08 GiB model files if they
reside in `/tmp`. No Cloud Run memory, latency, workload federation or production
Rekognition chain was tested by this service task. A 12-frame video plus cold
downloads may exceed the 240-second inference deadline; bounded frame batching
and full video acceptance remain pending. Do not claim the maximum video size
has passed. The service security/contract/cleanup suite has 34 passing tests.

Historical v2 manifest, now archived at
`config/manifests/ecoguard-models-2026-10-07-v2.json`, version
`ecoguard-models-2026-10-07-v2`, exact file SHA-256:
`6947e779fb740f252e35cff6f4ea90f03a87a3fe07d52d1c924bc8319ab1f2a6`.
Point `MODEL_MANIFEST_PATH` at the selected locked file; the Docker default intentionally
points at a failing example until deployment supplies the actual configuration.
