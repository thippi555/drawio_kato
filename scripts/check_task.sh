#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <task_id> [bucket] [table]" >&2
  exit 1
fi

TASK_ID="$1"
BUCKET="${2:-drawio-kato-artifacts}"
TABLE="${3:-ai_agent_tasks}"
REGION="${AWS_REGION:-ap-northeast-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "Task: ${TASK_ID}"
echo

echo "DynamoDB status:"
aws dynamodb get-item \
  --table-name "${TABLE}" \
  --region "${REGION}" \
  --key "{\"task_id\":{\"S\":\"${TASK_ID}\"}}" \
  --projection-expression "#s,error_message,bedrock_text_s3_path,output_s3_path,github_path" \
  --expression-attribute-names '{"#s":"status"}' \
  --output json

echo
echo "S3 intermediate outputs:"
aws s3 ls "s3://${BUCKET}/tasks/${TASK_ID}/" --recursive || true

echo
echo "S3 generated outputs:"
aws s3 ls "s3://${BUCKET}/outputs/${TASK_ID}/" --recursive || true
