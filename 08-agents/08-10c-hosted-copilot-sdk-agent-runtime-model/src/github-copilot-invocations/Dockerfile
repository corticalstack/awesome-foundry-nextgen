# Pulled from Microsoft Container Registry instead of Docker Hub to avoid
# the unauthenticated pull rate limit that breaks ACR remote builds with
# `toomanyrequests: You have reached your unauthenticated pull rate limit`.
# MCR's devcontainers/python image is Microsoft-hosted, so ACR can pull it
# without anonymous-rate throttling. The image is bigger than python:3.12-slim
# (it bundles dev tools), but for a hosted-agent demo that's an acceptable
# tradeoff for a reliable build.
FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

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

