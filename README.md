# drawio_kato

AWS Bedrock を利用した個人向けAIエージェント基盤のPoCリポジトリ。

## 目的

- AIエージェントによるタスク実行
- Markdown設計書生成
- draw.io構成図生成
- S3への成果物保存
- GitHubへの成果物反映

## 構成

```text
docs/           設計書
architecture/   draw.io構成図
prompts/        AIプロンプト
lambda/         Lambdaコード
stepfunctions/  Step Functions ASL
terraform/      AWS IaC
```

## PoCフロー

```text
User
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
GitHub
```

## 実装メモ

初期PoCでは `lambda/lambda_function.py` の単一Lambdaに複数アクションを集約する。
将来的に `task_receiver`、`prompt_builder`、`bedrock_invoker`、`output_formatter`、`github_writer` へ分割する。

Bedrockモデルは低コストPoC向けに `global.anthropic.claude-haiku-4-5-20251001-v1:0` を標準とする。

## 成果物の取り込み

GitHubへの自動Pushは初期PoCでは使わない。
S3に生成された成果物を確認してから、必要なものだけ手動でリポジトリへ取り込む。

```bash
./scripts/download_artifacts.sh <task_id>
git diff
```

取り込み先:

```text
docs/generated/<task_id>.md
architecture/generated/<task_id>.drawio
samples/<task_id>.json
```
