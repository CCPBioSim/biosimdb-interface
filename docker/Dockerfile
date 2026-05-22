FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for MDAnalysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*


# Copy schema files into the image
COPY ../biosim-schema/schema_webformfields.json /app/schema_webformfields.json
COPY ../biosim-schema/schema_enginemappings.json /app/schema_enginemappings.json
COPY ../biosim-schema/biosim_schema/schema/biosim_schema.yaml /app/biosim_schema.yaml

# Set environment variables to point to these files inside the container
ENV WEBFORM_SCHEMA_PATH=/app/schema_webformfields.json
ENV ENGINE_MAPPING_SCHEMA_PATH=/app/schema_enginemappings.json
ENV BIOSIM_SCHEMA_PATH=/app/biosim_schema.yaml

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
