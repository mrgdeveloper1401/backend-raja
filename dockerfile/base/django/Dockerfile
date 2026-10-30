# =========================
# Stage 1: Builder
# =========================
FROM python:3.14-alpine AS builder

WORKDIR /app

COPY requirements.txt .

RUN cp /dev/null /etc/apk/repositories && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/main" >> /etc/apk/repositories && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/community" >> /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add --no-cache \
        bash \
        curl \
        gcc \
        python3-dev \
        musl-dev \
        libpq-dev \
        linux-headers \
        build-base \
        rust \
        cargo \
    && pip config --user set global.index-url https://mirror-pypi.runflare.com/simple \
    && pip config --user set global.trusted-host mirror-pypi.runflare.com \
    && pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# =========================
# Stage 2: Production
# =========================
FROM python:3.14-alpine AS production

WORKDIR /app

RUN cp /dev/null /etc/apk/repositories && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/main" >> /etc/apk/repositories && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/community" >> /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add --no-cache \
        bash \
        curl \
        libpq \
    && pip config --user set global.index-url https://mirror-pypi.runflare.com/simple \
    && pip config --user set global.trusted-host mirror-pypi.runflare.com \
    && pip install --upgrade pip

COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels
