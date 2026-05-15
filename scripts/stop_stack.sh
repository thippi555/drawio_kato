#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUCKET="${ARTIFACT_BUCKET:-drawio-kato-artifacts}"

cd "${REPO_ROOT}"

cat <<EOF
This will delete the Terraform-managed AWS resources for this PoC.

Before stopping, make sure important artifacts have been downloaded from:
  s3://${BUCKET}/outputs/

The script can empty the artifact bucket before terraform destroy.
EOF

read -r -p "Empty s3://${BUCKET} before destroy? Type 'empty' to empty it, or press Enter to skip: " EMPTY_CONFIRM
if [[ "${EMPTY_CONFIRM}" == "empty" ]]; then
  echo "Emptying s3://${BUCKET}..."
  aws s3 rm "s3://${BUCKET}" --recursive
else
  echo "Skipping bucket empty step."
fi

read -r -p "Type 'destroy' to run terraform destroy: " DESTROY_CONFIRM
if [[ "${DESTROY_CONFIRM}" != "destroy" ]]; then
  echo "Canceled."
  exit 0
fi

(
  cd terraform
  terraform destroy
)

echo "Stack has been destroyed."
