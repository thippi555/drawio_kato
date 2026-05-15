#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: run_task.sh [--no-wait] [--timeout seconds] <input_text> [api_endpoint]

Default behavior:
  1. Submit task
  2. Wait until generated outputs are available
  3. Download artifacts into docs/generated, architecture/generated, samples
EOF
}

WAIT_FOR_OUTPUTS=true
TIMEOUT_SECONDS=300

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-wait)
      WAIT_FOR_OUTPUTS=false
      shift
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

INPUT_TEXT="$1"
API_ENDPOINT="${2:-${API_ENDPOINT:-https://xe6v1x8cy5.execute-api.ap-northeast-1.amazonaws.com}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHECK_SCRIPT="${SCRIPT_DIR}/check_task.sh"
DOWNLOAD_SCRIPT="${SCRIPT_DIR}/download_artifacts.sh"
BUCKET="${ARTIFACT_BUCKET:-drawio-kato-artifacts}"

TASK_ID="$(
  python3 - "$INPUT_TEXT" "$API_ENDPOINT" <<'PY'
import json
import sys
import urllib.request

input_text = sys.argv[1]
api_endpoint = sys.argv[2].rstrip("/")
url = f"{api_endpoint}/tasks"
payload = json.dumps({"input_text": input_text}, ensure_ascii=False).encode("utf-8")

request = urllib.request.Request(
    url,
    data=payload,
    method="POST",
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(request, timeout=30) as response:
    body = response.read().decode("utf-8")

print(body, file=sys.stderr)
data = json.loads(body)
print(data["task_id"])
PY
)"

echo
echo "task_id: ${TASK_ID}"
echo "check: ${CHECK_SCRIPT} ${TASK_ID}"
echo "download: ${DOWNLOAD_SCRIPT} ${TASK_ID}"

if [[ "${WAIT_FOR_OUTPUTS}" != "true" ]]; then
  exit 0
fi

echo
echo "Waiting for generated outputs..."
START_TIME="$(date +%s)"

while true; do
  if aws s3 ls "s3://${BUCKET}/outputs/${TASK_ID}/design.md" >/dev/null 2>&1 \
    && aws s3 ls "s3://${BUCKET}/outputs/${TASK_ID}/architecture.drawio" >/dev/null 2>&1 \
    && aws s3 ls "s3://${BUCKET}/outputs/${TASK_ID}/artifact.json" >/dev/null 2>&1; then
    break
  fi

  NOW="$(date +%s)"
  if (( NOW - START_TIME >= TIMEOUT_SECONDS )); then
    echo "Timed out waiting for outputs." >&2
    "${CHECK_SCRIPT}" "${TASK_ID}" || true
    exit 1
  fi

  sleep 5
done

echo "Generated outputs are ready."
"${DOWNLOAD_SCRIPT}" "${TASK_ID}" "${BUCKET}"

echo
echo "Local files:"
echo "  ${REPO_ROOT}/docs/generated/${TASK_ID}.md"
echo "  ${REPO_ROOT}/architecture/generated/${TASK_ID}.drawio"
echo "  ${REPO_ROOT}/samples/${TASK_ID}.json"
