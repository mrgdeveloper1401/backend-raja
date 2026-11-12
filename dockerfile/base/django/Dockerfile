# =========================
# Shared base
# =========================
FROM docker.arvancloud.ir/python:3.14-slim AS base

WORKDIR /app


# =========================
# Stage 1: Builder
# =========================
FROM base AS builder

#ENV PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple

# Build tools for psycopg[c].
RUN apt update \
    && apt install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip wheel \
        --no-cache-dir \
        --only-binary=django-bolt \
        --wheel-dir=/wheels \
        -r requirements.txt


# =========================
# Stage 2: Production
# =========================
FROM base AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt update \
    && apt install -y --no-install-recommends \
        bash \
        curl \
        ca-certificates \
        libpq5 \
        libgcc-s1 \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN python -m pip install \
        --no-cache-dir \
        --no-index \
        --find-links=/wheels \
        -r requirements.txt \
    && python -m pip check \
    && rm -rf /wheels
