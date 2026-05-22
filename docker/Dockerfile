FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for MDAnalysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy biosim-extractor and install it
COPY biosim-extractor /biosim-extractor
RUN pip install --no-cache-dir /biosim-extractor

# Install the package
COPY biosimdb-interface/pyproject.toml .
COPY biosimdb-interface/README.md .
COPY biosimdb-interface/LICENSE .
COPY biosimdb-interface /biosimdb-interface
RUN pip install --no-cache-dir /biosimdb-interface

# Copy schema files at a known path (mounted at runtime for dev — see below)
# COPY ../biosim-schema /biosim-schema

EXPOSE 5002

ENV FLASK_APP=biosimdb_interface

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "biosimdb_interface:create_app()"]
