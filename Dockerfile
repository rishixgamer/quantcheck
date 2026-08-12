# syntax=docker/dockerfile:1.7

# Both external images are immutable OCI-index digests.  Refresh them only via
# the documented dependency-update process and with a vulnerability scan.
ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd

FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS builder

ARG SOURCE_DATE_EPOCH=0
ENV PATH="/opt/quantcheck/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/quantcheck/.venv

WORKDIR /build
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md LICENSE .python-version ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable \
    && find /opt/quantcheck/.venv -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} + \
    && tar \
        --sort=name \
        --mtime="@${SOURCE_DATE_EPOCH}" \
        --owner=65532 \
        --group=65532 \
        --numeric-owner \
        --pax-option=delete=atime,delete=ctime \
        -C /opt/quantcheck \
        -cf /opt/quantcheck/venv.tar \
        .venv

FROM ${PYTHON_IMAGE} AS runtime

ARG SOURCE_DATE_EPOCH=0
ARG VCS_REF=unknown
ARG QUANTCHECK_VERSION=0.2.0.dev0
LABEL org.opencontainers.image.title="QuantCheck self-hosted audit runner" \
      org.opencontainers.image.description="Offline, single-tenant financial-data audit batch image" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/rishixgamer/quantcheck" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${QUANTCHECK_VERSION}"

ENV PATH="/opt/quantcheck/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1 \
    DO_NOT_TRACK=1 \
    QUANTCHECK_TELEMETRY=0 \
    QUANTCHECK_CONFIG_PATH=/config/run.json \
    QUANTCHECK_INPUT_DIR=/input \
    QUANTCHECK_OUTPUT_DIR=/output \
    QUANTCHECK_WORK_DIR=/work \
    TMPDIR=/work \
    HOME=/nonexistent

WORKDIR /opt/quantcheck
RUN --mount=type=bind,from=builder,source=/opt/quantcheck/venv.tar,target=/tmp/venv.tar \
    tar -xf /tmp/venv.tar -C /opt/quantcheck
COPY --chown=65532:65532 deploy/smoke /opt/quantcheck/smoke

# /config and /input are mount points for read-only customer material.
# /output and /work are the only intended writable mount points.  No VOLUME
# declaration is used, so the operator owns retention and deletion explicitly.
RUN install -d -m 0750 -o 65532 -g 65532 /config /input /output /work

USER 65532:65532
ENTRYPOINT ["/opt/quantcheck/.venv/bin/python", "-m", "quantcheck.external_dataset_self_hosted"]
