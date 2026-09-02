# Optional reproducible runner for `planlint`. Not required for local dev —
# `pip install planlint` (or `pip install -e ".[dev]"` for a checkout) is the
# primary path. This image is not built in CI, so a pyproject change can break
# it silently; `tests/test_agent_artifacts.py` pins the COPY set it depends on. This image pins a Python
# version for CI sandboxes that want a hermetic, dependency-free CLI invocation.
# Build:  docker build -t planlint .
# Run:    docker run --rm -v "$PWD":/repo planlint --target /repo validate

FROM python:3.12-slim

WORKDIR /app

# Install the package and its runtime deps only (no dev extras in the image).
# README.md is required by pyproject's `readme`. LICENSE is copied ahead of
# need: the PEP 639 migration tracked in docs/next-steps.md adds a
# `license-files` glob, which would fail this image build while the repo
# build stayed green -- a coupling that is cheap to pre-empt and easy to miss.
COPY pyproject.toml README.md LICENSE ./
COPY openspec_graph ./openspec_graph
RUN pip install --no-cache-dir .

WORKDIR /repo
ENTRYPOINT ["planlint"]
