# C local container verification - 2026-10-23

This record covers local Docker builds on Apple Silicon using Linux amd64
emulation. It is not cloud deployment, model accuracy or end-to-end acceptance.

## Build inputs

- Repository work starts from `f9a9e7a` with C's reviewed changes.
- Both build commands explicitly select `linux/amd64` through
  `scripts/build_containers.py` and load into the local Docker engine.
- Official Python base, Linux amd64 manifest:
  `python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0`.
- AWS ingest tag: `ecoguard-ingest:c-20261023-1`.
- AWS `docker image inspect` ID: `sha256:2fca6cdfe47846d8f7ce53723fcc0bf47750141290d8c1bcfe93c07795df3dc6`.

Image IDs identify these local build outputs; they are not published registry
addresses and do not establish reproducibility of unpinned OS packages.

## AWS ingest checks: passed

The real image build completed, including both hash-checked Python requirement
locks and `pip check`. A disposable container, with `--network none`, verified:

- imports of the handlers and Lambda RIC 4.2.2;
- the runtime remains uninitialized, so importing handlers does not create AWS clients;
- AWS configuration mode and packaged semantic calibration;
- installed `ffmpeg` and `ffprobe` executables;
- another successful `python -m pip check`.

No handler was invoked and no cloud credentials or host directories were mounted
for this smoke check. The image's default Lambda command was not used as a local
web server; the smoke check explicitly selected the Python entrypoint.

All **18 AWS infrastructure tests passed** inside the same image with networking
disabled. Tests used a read-only export of tracked source and a temporary writable
`tmp` directory, with no cloud credentials. This resolves the earlier host-Python
limitation where one existing shutdown test could not import `botocore`.
The suite uses offline fixtures/mocks; it does not inspect or suspend a cloud stack.

## Inference build repair

The first real build failed to resolve `torch==2.14.1+cpu`. The version exists in
the [official CPU wheel index](https://download.pytorch.org/whl/cpu/torch/).
pip's requirements-file `--index-url` replaces its existing index list, including
a command-line extra index; see the
[official pip parser](https://github.com/pypa/pip/blob/main/src/pip/_internal/req/req_file.py).
The fix records the CPU extra index immediately after PyPI inside the lock.
All dependency versions remain unchanged. The original uv generation command
selects the CPU backend but did not emit this extra-index directive; preserve it
when regenerating the lock.

A second startup check then exposed an eager `Path.parents[3]` lookup in
`Settings.from_env()`: the Docker path `/app/app/settings.py` is shallower than
the source tree. The fix preserves source defaults, uses `/config` in that
container layout, and continues to honor explicit environment paths. Three
regression tests cover source defaults, container defaults and environment
overrides; all passed.

## Inference checks: passed

- Final local tag: `ecoguard-inference:c-20261023-3`.
- `docker image inspect` ID: `sha256:7e481399309c8a90276c864e9765545657e44c00e9061ee668b4e56db4f22fdb`.
- Linux amd64 build completed with the unchanged `torch==2.14.1+cpu` pin.
- An offline container verified default and locked-manifest health responses,
  `/readyz` returning 503 while weights are unloaded, and unauthenticated
  `/v1/warmup` returning 401. The locked manifest matched SHA-256
  `639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae`.
- Health checks did not import Torch/Transformers or create a model process.
  Separate checks imported the model runtime classes, verified the CPU-only
  Torch version, executed a CPU tensor operation, and passed `pip check`.
- A disposable container using the unmodified default Docker command started
  uvicorn. HTTP requests over container loopback returned health 200,
  readiness 503 and unauthenticated warmup 401. No host ports were published.

All these containers used `--network none`, received no credentials, and were
removed afterward. No model weights were downloaded or inference run. The
ASGI test client emitted a Starlette deprecation warning about its httpx
adapter; the checks and real uvicorn startup passed without changing dependency
versions. The Docker build also emitted a heuristic warning about the existing
`SERVICE_AUTH_MODE` name; that variable selects an authentication mode and
contains no credential.

## Reproduce local builds

Run from the repository root with a running Linux Docker engine and amd64
emulation where required. These commands build and load locally, without a
registry push or cloud deployment:

```sh
ECOGUARD_BASE_IMAGE='python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0'
python3 scripts/build_containers.py aws-ingest --image ecoguard-ingest:c-20261023-1 --base-image "$ECOGUARD_BASE_IMAGE" --aws-lambda-ric-version 4.2.2 --build
python3 scripts/build_containers.py inference --image ecoguard-inference:c-20261023-3 --base-image "$ECOGUARD_BASE_IMAGE" --build
PYTHONPATH=services/inference python3 -m unittest discover -s services/inference/tests -p test_settings.py -v
```

## Build command security review

SonarCloud flagged the command formatter and build execution. Review found a
PowerShell copy/paste edge case: a checkout directory can contain smart single
quotes, which PowerShell treats as string delimiters. The formatter now doubles
all five PowerShell single-quote characters, following the
[PowerShell quoting rules](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules).
The ASCII CLI allowlists remain unchanged. Actual builds execute the argument
list with explicit `shell=False`; the rendered command is display-only, as
recommended by the [Python subprocess security guidance](https://docs.python.org/3/library/subprocess.html#security-considerations).

All **11 build-helper tests passed**, including hostile CLI input rejection,
smart-quote path rendering and mocked successful argv execution without a shell.
PowerShell is not installed on this host, so the quoting regression checks the
rendered literals rather than executing an external PowerShell process. No
Sonar rule, quality gate or security annotation was disabled or marked resolved.
The remote analysis result must be reviewed separately.

## Remaining C work

Registry publication, a real Lambda ZIP, saved cloud plans, infrastructure apply,
AWS-to-Google WIF, service IAM/TLS/CORS checks, model warmup and real media
processing remain outstanding. No cloud resources or trust were changed by
these local checks. Continue to respect the A$0 additional personal-spend limit.

Prepared with Codex assistance; review and understand the commands and evidence
before the individual demonstration.
