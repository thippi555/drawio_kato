# AIエージェント基盤 アーキテクチャ設計書 v0.1

## 1. 概要

本書は AIエージェント基盤の AWS アーキテクチャを定義する。

本システムは、Amazon Bedrock を中心に、Lambda、Step Functions、S3、DynamoDB、GitHub を組み合わせ、AIによるタスク実行、設計書生成、構成図生成を行う。

個人利用を前提とし、低コスト・サーバレス・段階的拡張を基本方針とする。

---

## 2. 全体アーキテクチャ

```text
利用者
  ↓
GitHub / CLI / Web UI
  ↓
API Gateway
  ↓
Lambda
  ↓
Step Functions
  ↓
Amazon Bedrock
  ↓
S3 / DynamoDB
  ↓
GitHub Repository
```

---

## 3. PoC実装アーキテクチャ

### 3.1 処理単位

PoCでは単一Lambda関数 `task_processor` に複数アクションを持たせる。

```json
{
  "lambda": {
    "function_name": "drawio-kato-task-processor",
    "actions": [
      "receive_task",
      "build_prompt",
      "invoke_bedrock",
      "format_output",
      "write_github",
      "mark_failed"
    ]
  }
}
```

将来的に処理量や責務が増えた場合は、以下の単位へ分割する。

```json
{
  "future_lambdas": [
    "task_receiver",
    "prompt_builder",
    "bedrock_invoker",
    "output_formatter",
    "github_writer"
  ]
}
```

---

## 4. Step Functions

### 4.1 タスクフロー

```json
{
  "flow": [
    "BuildPrompt",
    "InvokeBedrock",
    "FormatOutput",
    "WriteGitHub"
  ],
  "error_flow": "MarkFailed"
}
```

### 4.2 状態遷移

```text
ACCEPTED
  ↓
STARTED
  ↓
PROMPT_BUILT
  ↓
BEDROCK_INVOKED
  ↓
OUTPUT_FORMATTED
  ↓
COMPLETED
```

異常時は `FAILED` とし、DynamoDB の `error_message` に原因を保存する。

---

## 5. データ設計

### 5.1 DynamoDB

テーブル名は `ai_agent_tasks` とする。

```json
{
  "table_name": "ai_agent_tasks",
  "partition_key": "task_id",
  "billing_mode": "PAY_PER_REQUEST",
  "attributes": {
    "task_id": "string",
    "status": "string",
    "input_text": "string",
    "prompt_s3_path": "string",
    "bedrock_raw_s3_path": "string",
    "output_s3_path": "string",
    "github_path": "string",
    "created_at": "string",
    "updated_at": "string",
    "error_message": "string"
  }
}
```

### 5.2 S3

バケット名は `drawio-kato-artifacts` とする。

```text
s3://drawio-kato-artifacts/
 ├── tasks/
 ├── outputs/
 ├── prompts/
 └── logs/
```

---

## 6. API

### 6.1 タスク登録

```http
POST /tasks
Content-Type: application/json
```

```json
{
  "input_text": "Lambda + Bedrock + S3 の構成図を作成してください"
}
```

レスポンス:

```json
{
  "task_id": "uuid",
  "status": "STARTED"
}
```

---

## 7. 成果物

Bedrockの出力はJSONとして扱う。

```json
{
  "markdown": "Markdown設計書",
  "drawio_xml": "draw.io XML",
  "artifact_json": {
    "title": "string",
    "nodes": [],
    "edges": [],
    "aws_services": [],
    "files": []
  }
}
```

S3保存先:

```text
outputs/{task_id}/design.md
outputs/{task_id}/architecture.drawio
outputs/{task_id}/artifact.json
```

GitHub保存先:

```text
docs/generated/{task_id}.md
architecture/generated/{task_id}.drawio
samples/{task_id}.json
```
