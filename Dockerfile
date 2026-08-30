# Optional reproducible runner for `specgraph`. Not required for local dev —
# `pip install -e ".[dev]"` is the primary path. This image pins a Python
# version for CI sandboxes that want a hermetic, dependency-free CLI invocation.
# Build:  docker build -t specgraph .
# Run:    docker run --rm -v "$PWD":/repo specgraph --target /repo validate

FROM python:3.12-slim

WORKDIR /app

# Install the package and its runtime deps only (no dev extras in the image).
COPY pyproject.toml README.md ./
COPY openspec_graph ./openspec_graph
RUN pip install --no-cache-dir .

WORKDIR /repo
ENTRYPOINT ["specgraph"]
