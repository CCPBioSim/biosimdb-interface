# Stage 1: Fetch Schema Artifacts
FROM ubuntu:24.04 AS schema-fetcher

RUN apt-get update && apt-get install -y --no-install-recommends curl jq tar ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /tmp

RUN TAG=$(curl -fsSL https://api.github.com/repos/CCPBioSim/biosim-schema/releases/latest | jq -r .tag_name) && \
    curl -fsSL -o artifacts.tar.gz \
    "https://github.com/CCPBioSim/biosim-schema/releases/download/${TAG}/biosim-schema-artifacts.tar.gz" && \
    mkdir -p /opt/biosim-schema && \
    tar -xzf artifacts.tar.gz -C /opt/biosim-schema


# Stage 2: Build Python dependencies
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv /venv

# Activate venv and install dependencies
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY biosimdb_interface/ biosimdb_interface/

# Install application and its dependencies into the venv
RUN pip install --upgrade pip setuptools && \
    pip install --no-cache-dir gunicorn .


# Stage 3: Runtime
FROM ubuntu:24.04

ARG PORT=5002

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-minimal \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 10001 biosim && \
    useradd \
      --uid 10001 \
      --gid biosim \
      --create-home \
      --shell /usr/sbin/nologin \
      biosim

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder --chown=biosim:biosim /venv /venv

# Copy schema artifacts from the fetcher stage
COPY --from=schema-fetcher --chown=biosim:biosim /opt/biosim-schema /opt/biosim-schema

# Set PATH to include the virtual environment's bin directory
ENV PATH="/venv/bin:$PATH"

USER biosim

ENV PORT=${PORT} \
    FLASK_APP=biosimdb_interface \
    PYSTOW_HOME=/app/.pystow \
    WEBFORM_SCHEMA_PATH=/opt/biosim-schema/project/schema_webformfields.json \
    ENGINE_MAPPING_SCHEMA_PATH=/opt/biosim-schema/project/schema_enginemappings.json \
    BIOSIM_SCHEMA_PATH=/opt/biosim-schema/biosim_schema/schema/biosim_schema.yaml

EXPOSE ${PORT}

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT 'biosimdb_interface:create_app()'"]
