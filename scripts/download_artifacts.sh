#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <task_id> [bucket]" >&2
  exit 1
fi

TASK_ID="$1"
BUCKET="${2:-drawio-kato-artifacts}"
BASE_S3="s3://${BUCKET}/outputs/${TASK_ID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

mkdir -p docs/generated architecture/generated samples

aws s3 cp "${BASE_S3}/design.md" "docs/generated/${TASK_ID}.md"
aws s3 cp "${BASE_S3}/architecture.drawio" "architecture/generated/${TASK_ID}.drawio"
aws s3 cp "${BASE_S3}/artifact.json" "samples/${TASK_ID}.json"

echo "Downloaded artifacts for task: ${TASK_ID}"
echo "  docs/generated/${TASK_ID}.md"
echo "  architecture/generated/${TASK_ID}.drawio"
echo "  samples/${TASK_ID}.json"
