FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for native extensions (pykakasi, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata first to leverage Docker layer caching
COPY pyproject.toml .

# Install the project dependencies (without the source, so this layer is
# cached unless pyproject.toml changes)
RUN pip install --no-cache-dir .

# Now copy in the full source tree and install in editable mode so the
# console script entry point resolves correctly.
COPY . .
RUN pip install --no-cache-dir -e .

# Ensure the data directory exists for volume mounting
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "entity_resolution.main:app", "--host", "0.0.0.0", "--port", "8000"]
