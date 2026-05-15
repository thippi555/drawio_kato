#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "Packaging Lambda..."
mkdir -p lambda/dist
(
  cd lambda
  zip -q -r dist/lambda_function.zip lambda_function.py
)

echo "Applying Terraform..."
(
  cd terraform
  terraform init
  terraform apply
)

echo "Stack is ready."
