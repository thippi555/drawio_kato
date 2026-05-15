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
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
)
OUTPUT_SCHEMA_VERSION = "2026-05-15.1"
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

このプロジェクトの固定情報:
- project_name: drawio_kato
- repository: https://github.com/thippi555/drawio_kato
- aws_region: ap-northeast-1
- api_route: POST /tasks
- lambda_function: drawio-kato-task-processor
- state_machine: drawio-kato-task-flow
- artifact_bucket: drawio-kato-artifacts
- task_table: ai_agent_tasks
- bedrock_model_id: {BEDROCK_MODEL_ID}
- runtime: python3.12
- iac: Terraform
- storage_prefixes: tasks/, outputs/, prompts/, logs/
- output_files: design.md, architecture.drawio, artifact.json

必須出力:
1. markdown: 設計書Markdown
2. drawio_xml: draw.io XML
3. artifact_json: 構造化JSON

制約:
- トップレベルキーは markdown, drawio_xml, artifact_json の3つのみ
- markdown と drawio_xml は文字列
- artifact_json はJSONオブジェクト
- 上記の固定情報と矛盾する名前、サービス、ファイル構成を出さない
- SAM、Cognito、VPC、入力用S3バケットは出力しない
- 複数Lambda分割は将来拡張としてのみ扱う
- 個人利用、低コスト、サーバレス中心
- AWS構成はAPI Gateway、Lambda、Step Functions、Bedrock、S3、DynamoDBを優先
- 実装済みフローは User → API Gateway → Lambda → Step Functions → Bedrock → S3/DynamoDB
- GitHub保存しやすいファイル名を含める
- JSONとしてパース可能な形式のみ返す。末尾まで必ず閉じる
- Markdownコードブロックや説明文は付けない
- drawio_xml は有効な mxfile XML とし、主要ノードと矢印を含める
- artifact_json には system, services, workflow, storage, dynamodb, files, future_extensions を含める

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
        "max_tokens": 8192,
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
    raw_key = f"tasks/{task_id}/bedrock_raw.json"
    text_key = f"tasks/{task_id}/bedrock_text.txt"
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=raw_key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=text_key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    _update_task(
        task_id,
        status="BEDROCK_INVOKED",
        bedrock_raw_s3_path=f"s3://{ARTIFACT_BUCKET}/{raw_key}",
        bedrock_text_s3_path=f"s3://{ARTIFACT_BUCKET}/{text_key}",
    )
    return {
        "task_id": task_id,
        "input_text": event["input_text"],
        "prompt_s3_path": event["prompt_s3_path"],
        "bedrock_raw_s3_path": f"s3://{ARTIFACT_BUCKET}/{raw_key}",
        "bedrock_text_s3_path": f"s3://{ARTIFACT_BUCKET}/{text_key}",
    }


def format_output(event: Dict[str, Any]) -> Dict[str, Any]:
    task_id = event["task_id"]
    bedrock_text = event.get("bedrock_text") or _read_s3_uri(event["bedrock_text_s3_path"])
    try:
        output = _parse_json_text(bedrock_text)
    except json.JSONDecodeError as exc:
        output = {
            "markdown": bedrock_text,
            "drawio_xml": _minimal_drawio_xml({"metadata": {"title": "AI Agent Architecture"}}),
            "artifact_json": {
                "parse_error": str(exc),
                "source": event.get("bedrock_text_s3_path"),
            },
        }
    normalized = _normalize_output(output, bedrock_text)
    normalized["artifact_json"] = _enrich_artifact_json(normalized["artifact_json"], task_id)
    markdown = normalized["markdown"]
    drawio_xml = normalized["drawio_xml"]
    artifact_json = normalized["artifact_json"]

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
        "formatted_output": normalized,
        "output_s3_path": f"s3://{ARTIFACT_BUCKET}/outputs/{task_id}/",
        "github_files": [
            {"path": f"docs/generated/{task_id}.md", "s3_path": f"s3://{ARTIFACT_BUCKET}/{keys['markdown']}"},
            {"path": f"architecture/generated/{task_id}.drawio", "s3_path": f"s3://{ARTIFACT_BUCKET}/{keys['drawio']}"},
            {
                "path": f"samples/{task_id}.json",
                "s3_path": f"s3://{ARTIFACT_BUCKET}/{keys['json']}",
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
        content = file_item.get("content")
        if content is None and file_item.get("s3_path"):
            content = _read_s3_uri(file_item["s3_path"])
        if content is None:
            content = ""
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
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("json"):
        stripped = stripped[4:].strip()
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def _normalize_output(output: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    outputs = output.get("outputs", {}) if isinstance(output.get("outputs"), dict) else {}
    markdown = _content_value(output.get("markdown")) or _content_value(outputs.get("markdown"))
    drawio_xml = (
        _content_value(output.get("drawio_xml"))
        or _content_value(outputs.get("drawio_xml"))
        or _content_value(outputs.get("drawio"))
    )
    artifact_json = output.get("artifact_json") or outputs.get("artifact_json") or output

    if not markdown:
        markdown = raw_text
    if not drawio_xml:
        drawio_xml = _minimal_drawio_xml(output)

    return {
        "markdown": markdown,
        "drawio_xml": drawio_xml,
        "artifact_json": artifact_json,
    }


def _enrich_artifact_json(artifact_json: Any, task_id: str) -> Dict[str, Any]:
    if not isinstance(artifact_json, dict):
        artifact_json = {"value": artifact_json}
    artifact_json.setdefault("system", {})
    artifact_json["system"].update(
        {
            "project_name": "drawio_kato",
            "repository": "https://github.com/thippi555/drawio_kato",
            "aws_region": "ap-northeast-1",
            "api_route": "POST /tasks",
            "lambda_function": "drawio-kato-task-processor",
            "state_machine": "drawio-kato-task-flow",
            "bedrock_model_id": BEDROCK_MODEL_ID,
        }
    )
    artifact_json.setdefault("storage", {})
    artifact_json["storage"].update(
        {
            "artifact_bucket": ARTIFACT_BUCKET,
            "output_prefix": f"outputs/{task_id}/",
            "task_prefix": f"tasks/{task_id}/",
        }
    )
    artifact_json.setdefault("dynamodb", {"table_name": TASK_TABLE_NAME, "partition_key": "task_id"})
    artifact_json.setdefault(
        "files",
        [
            f"outputs/{task_id}/design.md",
            f"outputs/{task_id}/architecture.drawio",
            f"outputs/{task_id}/artifact.json",
        ],
    )
    artifact_json["future_extensions"] = _filter_future_extensions(artifact_json.get("future_extensions", []))
    artifact_json["schema_version"] = OUTPUT_SCHEMA_VERSION
    return artifact_json


def _filter_future_extensions(value: Any) -> Any:
    blocked_terms = ("sam", "cognito", "vpc", "input bucket", "input-only s3")
    if not isinstance(value, list):
        return value
    filtered = []
    for item in value:
        text = json.dumps(item, ensure_ascii=False).lower()
        if any(term in text for term in blocked_terms):
            continue
        filtered.append(item)
    return filtered


def _content_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content") or value.get("body") or value.get("text")
        if isinstance(content, str):
            return content
    return ""


def _minimal_drawio_xml(output: Dict[str, Any]) -> str:
    title = (
        output.get("metadata", {}).get("title")
        if isinstance(output.get("metadata"), dict)
        else "AI Agent Architecture"
    )
    return (
        '<mxfile host="app.diagrams.net">'
        '<diagram name="Architecture">'
        '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="title" value="{_xml_escape(title)}" style="text;html=1;" vertex="1" parent="1">'
        '<mxGeometry x="40" y="40" width="240" height="40" as="geometry"/></mxCell>'
        "</root></mxGraphModel></diagram></mxfile>"
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _put_text(key: str, content: str, content_type: str) -> None:
    s3.put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type,
    )


def _read_s3_uri(uri: str) -> str:
    prefix = "s3://"
    if not uri.startswith(prefix):
        raise ValueError(f"Unsupported S3 URI: {uri}")
    bucket_and_key = uri[len(prefix) :]
    bucket, key = bucket_and_key.split("/", 1)
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


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
