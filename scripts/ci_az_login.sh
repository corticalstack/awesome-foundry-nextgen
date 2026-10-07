#!/usr/bin/env bash
# Sign the Azure CLI in again with the newest GitHub OIDC token.
#
# GitHub's OIDC tokens expire after 5 minutes, and az keeps using the one it
# logged in with to get tokens for scopes it has not cached yet, which then fails
# with AADSTS700024 ("Client assertion is not within its valid time range").
# The live notebook workflow keeps a fresh token in $AZURE_FEDERATED_TOKEN_FILE
# and runs this before each notebook (scripts/run_notebooks.py --before-each).
set -euo pipefail
az login --service-principal --username "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID" \
  --federated-token "$(cat "$AZURE_FEDERATED_TOKEN_FILE")" --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID" --output none
