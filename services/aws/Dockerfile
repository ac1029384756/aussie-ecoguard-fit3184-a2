# Build from the repository root. Pin BASE_IMAGE to a verified digest for release.
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /var/task
COPY services/aws/requirements.lock.txt ./requirements.lock.txt
COPY services/aws/requirements-ric.lock.txt ./requirements-ric.lock.txt
# Require the caller to select the committed RIC version; never append an unhashed requirement.
ARG AWS_LAMBDA_RIC_VERSION
RUN python -c 'import os, sys; from pathlib import Path; \
    expected = "awslambdaric==" + os.environ.get("AWS_LAMBDA_RIC_VERSION", ""); \
    entries = (line.split()[0] for line in Path("requirements-ric.lock.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")); \
    sys.exit(0 if expected in entries else "AWS_LAMBDA_RIC_VERSION must match requirements-ric.lock.txt")' \
    && python -m pip install --no-cache-dir --require-hashes \
        --only-binary=awslambdaric,simplejson,snapshot-restore-py \
        -r requirements.lock.txt -r requirements-ric.lock.txt \
    && python -m pip check
COPY packages/domain/ecoguard_domain ./ecoguard_domain
COPY services/aws/ecoguard_aws ./ecoguard_aws
ENV ECO_MODE=aws PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["ecoguard_aws.handlers.api"]
