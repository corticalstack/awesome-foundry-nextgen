# Pulled from Microsoft Container Registry instead of Docker Hub to avoid
# the unauthenticated pull rate limit that breaks ACR remote builds with
# `toomanyrequests: You have reached your unauthenticated pull rate limit`.
# MCR's devcontainers/python image is Microsoft-hosted, so ACR can pull it
# without anonymous-rate throttling. It also bundles git + build tools the
# agent's shell may use. Built linux/amd64 to match Foundry's hosted runtime,
# which is also the platform the claude-agent-sdk wheel's bundled `claude`
# binary targets.
# Pinned to the release 3.12-bookworm pointed to on 2026-10-06. requirements.txt
# is compiled for its glibc (2.36), so recompile it when this changes.
FROM mcr.microsoft.com/devcontainers/python:3.2.3-3.12-bookworm

WORKDIR /app

COPY . user_agent/
WORKDIR /app/user_agent

RUN pip install --no-input --upgrade pip && \
    if [ -f requirements.txt ]; then \
    pip install --no-input -r requirements.txt; \
    else \
    echo "No requirements.txt found"; \
    fi

EXPOSE 8088

CMD ["python", "main.py"]
