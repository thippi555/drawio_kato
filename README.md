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
