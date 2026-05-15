#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input_text> [api_endpoint]" >&2
  exit 1
fi

INPUT_TEXT="$1"
API_ENDPOINT="${2:-${API_ENDPOINT:-https://xe6v1x8cy5.execute-api.ap-northeast-1.amazonaws.com}}"

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

print(body)

try:
    data = json.loads(body)
except json.JSONDecodeError:
    sys.exit(0)

task_id = data.get("task_id")
if task_id:
    print()
    print(f"task_id: {task_id}")
    print(f"check: ./scripts/check_task.sh {task_id}")
    print(f"download: ./scripts/download_artifacts.sh {task_id}")
PY
