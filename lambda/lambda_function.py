import base64
import json
import os
import time
import traceback
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import boto3


dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
stepfunctions = boto3.client("stepfunctions")
bedrock_runtime = boto3.client("bedrock-runtime")
secretsmanager = boto3.client("secretsmanager")


TASK_TABLE_NAME = os.environ.get("TASK_TABLE_NAME", "ai_agent_tasks")
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "drawio-kato-artifacts")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
)
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "thippi555")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "drawio_kato")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN_SECRET_ID = os.environ.get("GITHUB_TOKEN_SECRET_ID", "")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        action = event.get("action") or _route_action(event)
        if action == "receive_task":
            return receive_task(event)
        if action == "build_prompt":
            return build_prompt(event)
        if action == "invoke_bedrock":
            return invoke_bedrock(event)
        if action == "format_output":
            return format_output(event)
        if action == "write_github":
            return write_github(event)
        if action == "mark_failed":
            return mark_failed(event)
        raise ValueError(f"Unknown action: {action}")
    except Exception as exc:
        task_id = event.get("task_id") or event.get("pathParameters", {}).get("task_id")
        if task_id:
            _update_task(task_id, status="FAILED", error_message=str(exc))
        print(traceback.format_exc())
        raise


def receive_task(event: Dict[str, Any]) -> Dict[str, Any]:
    body = _parse_body(event)
    input_text = body.get("input_text") or body.get("task") or body.get("prompt")
    if not input_text:
        return _api_response(400, {"message": "input_text is required"})

    now = _now()
    task_id = str(uuid4())
    item = {
        "task_id": task_id,
        "status": "ACCEPTED",
        "input_text": input_text,
        "created_at": now,
        "updated_at": now,
    }
    _table().put_item(Item=item)

    workflow_input = {"task_id": task_id, "input_text": input_text}
    if STATE_MACHINE_ARN:
        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"task-{task_id}",
            input=json.dumps(workflow_input, ensure_ascii=False),
        )
        status = "STARTED"
    else:
        status = "ACCEPTED"

    _update_task(task_id, status=status)
    return _api_response(202, {"task_id": task_id, "status": status})


def build_prompt(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event["task_id"]
    input_text = event["input_text"]
    prompt = f"""あなたはAWS Bedrockを利用したAIエージェント基盤の設計支援AIです。

以下のユーザー依頼を、AIが後続処理しやすい構造で成果物化してください。

必須出力:
1. markdown: 設計書Markdown
2. drawio_xml: draw.io XML
3. artifact_json: 構造化JSON

制約:
- 個人利用、低コスト、サーバレス中心
- AWS構成はAPI Gateway、Lambda、Step Functions、Bedrock、S3、DynamoDBを優先
- GitHub保存しやすいファイル名を含める
- JSONとしてパース可能な形式のみ返す

ユーザー依頼:
{input_text}
"""
    key = f"prompts/{task_id}.txt"
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=key,
        Body=prompt.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    _update_task(task_id, status="PROMPT_BUILT", prompt_s3_path=f"s3://{ARTIFACT_BUCKET}/{key}")
    return {**event, "prompt": prompt, "prompt_s3_path": f"s3://{ARTIFACT_BUCKET}/{key}"}


def invoke_bedrock(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event["task_id"]
    prompt = event["prompt"]
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }
    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(response["body"].read())
    text = "".join(part.get("text", "") for part in payload.get("content", []))
    key = f"tasks/{task_id}/bedrock_raw.json"
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    _update_task(task_id, status="BEDROCK_INVOKED", bedrock_raw_s3_path=f"s3://{ARTIFACT_BUCKET}/{key}")
    return {**event, "bedrock_text": text, "bedrock_raw_s3_path": f"s3://{ARTIFACT_BUCKET}/{key}"}


def format_output(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event["task_id"]
    output = _parse_json_text(event["bedrock_text"])
    markdown = output.get("markdown", "")
    drawio_xml = output.get("drawio_xml", "")
    artifact_json = output.get("artifact_json", output)

    keys = {
        "markdown": f"outputs/{task_id}/design.md",
        "drawio": f"outputs/{task_id}/architecture.drawio",
        "json": f"outputs/{task_id}/artifact.json",
    }
    _put_text(keys["markdown"], markdown, "text/markdown; charset=utf-8")
    _put_text(keys["drawio"], drawio_xml, "application/xml; charset=utf-8")
    _put_text(keys["json"], json.dumps(artifact_json, ensure_ascii=False, indent=2), "application/json; charset=utf-8")

    result = {
        **event,
        "formatted_output": output,
        "output_s3_path": f"s3://{ARTIFACT_BUCKET}/outputs/{task_id}/",
        "github_files": [
            {"path": f"docs/generated/{task_id}.md", "content": markdown},
            {"path": f"architecture/generated/{task_id}.drawio", "content": drawio_xml},
            {
                "path": f"samples/{task_id}.json",
                "content": json.dumps(artifact_json, ensure_ascii=False, indent=2),
            },
        ],
    }
    _update_task(task_id, status="OUTPUT_FORMATTED", output_s3_path=result["output_s3_path"])
    return result


def write_github(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event["task_id"]
    files = event.get("github_files", [])
    if not GITHUB_TOKEN_SECRET_ID:
        _update_task(task_id, status="GITHUB_SKIPPED", github_path="GitHub token secret is not configured")
        return {**event, "github_status": "SKIPPED"}

    token = _get_github_token()
    written_paths = []
    for file_item in files:
        path = file_item["path"]
        content = file_item.get("content", "")
        _put_github_file(token, path, content, f"Add generated artifact for task {task_id}")
        written_paths.append(path)
        time.sleep(0.2)

    _update_task(task_id, status="COMPLETED", github_path=",".join(written_paths))
    return {**event, "github_status": "COMPLETED", "github_paths": written_paths}


def mark_failed(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event.get("task_id")
    error = event.get("error_message") or json.dumps(event.get("error", {}), ensure_ascii=False)
    if task_id:
        _update_task(task_id, status="FAILED", error_message=error)
    return {**event, "status": "FAILED"}


def _route_action(event: Dict[str, Any]) -> str:
    if "requestContext" in event:
        return "receive_task"
    return "receive_task"


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    body = event.get("body")
    if not body:
        return event
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)


def _parse_json_text(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    return json.loads(stripped)


def _put_text(key: str, content: str, content_type: str) -> None:
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type,
    )


def _put_github_file(token: str, path: str, content: str, message: str) -> None:
    encoded_path = urllib.parse.quote(path)
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{encoded_path}"
    sha = _get_github_sha(token, url)
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    _urlopen_json(request)


def _get_github_sha(token: str, url: str) -> str:
    request = urllib.request.Request(
        f"{url}?ref={GITHUB_BRANCH}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        data = _urlopen_json(request)
        return data.get("sha", "")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise


def _urlopen_json(request: urllib.request.Request) -> Dict[str, Any]:
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_github_token() -> str:
    secret = secretsmanager.get_secret_value(SecretId=GITHUB_TOKEN_SECRET_ID)
    raw = secret.get("SecretString", "")
    try:
        parsed = json.loads(raw)
        return parsed.get("token") or parsed.get("github_token") or raw
    except json.JSONDecodeError:
        return raw


def _table():
    return dynamodb.Table(TASK_TABLE_NAME)


def _update_task(task_id: str, **values: str) -> None:
    values["updated_at"] = _now()
    names = {f"#{key}": key for key in values}
    attr_values = {f":{key}": value for key, value in values.items()}
    expression = "SET " + ", ".join(f"#{key} = :{key}" for key in values)
    _table().update_item(
        Key={"task_id": task_id},
        UpdateExpression=expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=attr_values,
    )


def _api_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
