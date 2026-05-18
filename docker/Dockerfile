FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for MDAnalysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install the package
COPY pyproject.toml .
COPY README.md .
COPY LICENSE .
COPY biosimdb_interface/ biosimdb_interface/
RUN pip install --no-cache-dir .

# Copy schema files at a known path (mounted at runtime for dev — see below)
# COPY ../biosim-schema /biosim-schema

EXPOSE 5002

ENV FLASK_APP=biosimdb_interface

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "biosimdb_interface:create_app()"]
