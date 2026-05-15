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
scripts/        運用補助スクリプト
samples/        生成JSONサンプル
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
手動確認
  ↓
GitHub commit / push
```

## 前提

- AWS CLI が設定済みであること
- Terraform が利用できること
- Anthropic Claude の use case details が提出済みであること
- AWS Marketplace 経由のモデル利用が有効化済みであること
- Lambda ZIP を作成してから Terraform を適用すること

AWS認証確認:

```bash
aws sts get-caller-identity
```

## 実装メモ

初期PoCでは `lambda/lambda_function.py` の単一Lambdaに複数アクションを集約する。
将来的に `task_receiver`、`prompt_builder`、`bedrock_invoker`、`output_formatter`、`github_writer` へ分割する。

Bedrockモデルは低コストPoC向けに `global.anthropic.claude-haiku-4-5-20251001-v1:0` を標準とする。

## デプロイ

Lambda ZIP を作成する。

```bash
cd lambda
mkdir -p dist
zip -r dist/lambda_function.zip lambda_function.py
```

Terraform を適用する。

```bash
cd ../terraform
terraform init
terraform plan
terraform apply
```

出力される `api_endpoint` を控える。

```text
api_endpoint = "https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com"
artifact_bucket = "drawio-kato-artifacts"
task_table = "ai_agent_tasks"
```

## 実行手順

APIへタスクを投入する。

簡易実行スクリプト:

```bash
./scripts/run_task.sh "Lambda + Bedrock + S3 の構成図を作成してください"
```

直接 `curl` で実行する場合:

```bash
curl -X POST \
  https://xe6v1x8cy5.execute-api.ap-northeast-1.amazonaws.com/tasks \
  -H "Content-Type: application/json" \
  -d '{"input_text":"Lambda + Bedrock + S3 の構成図を作成してください"}'
```

レスポンス例:

```json
{
  "task_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "STARTED"
}
```

以降は返却された `task_id` を使う。

API endpoint を差し替える場合:

```bash
API_ENDPOINT="https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com" \
  ./scripts/run_task.sh "構成図を作成してください"
```

## 状態確認

DynamoDB の状態を確認する。

```bash
aws dynamodb get-item \
  --table-name ai_agent_tasks \
  --region ap-northeast-1 \
  --key '{"task_id":{"S":"<task_id>"}}' \
  --projection-expression "#s,error_message,bedrock_text_s3_path,output_s3_path,github_path" \
  --expression-attribute-names '{"#s":"status"}'
```

主なステータス:

```text
STARTED           Step Functions開始済み
PROMPT_BUILT      プロンプト作成済み
BEDROCK_INVOKED   Bedrock実行済み
OUTPUT_FORMATTED  成果物保存済み
GITHUB_SKIPPED    GitHub自動Push未設定のためスキップ
FAILED            失敗
```

初期PoCでは `GITHUB_SKIPPED` は正常終了扱いとする。

簡易確認スクリプト:

```bash
./scripts/check_task.sh <task_id>
```

このスクリプトは DynamoDB の状態、S3中間出力、S3成果物をまとめて表示する。

## S3確認

中間出力:

```bash
aws s3 ls s3://drawio-kato-artifacts/tasks/<task_id>/ --recursive
```

期待するファイル:

```text
tasks/<task_id>/bedrock_raw.json
tasks/<task_id>/bedrock_text.txt
```

成果物:

```bash
aws s3 ls s3://drawio-kato-artifacts/outputs/<task_id>/ --recursive
```

期待するファイル:

```text
outputs/<task_id>/design.md
outputs/<task_id>/architecture.drawio
outputs/<task_id>/artifact.json
```

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

取り込み後に差分を確認する。

```bash
git diff
git status
```

問題なければ commit / push する。

```bash
git add .
git commit -m "Add generated AI agent artifacts"
git push origin main
```

## Lambda更新手順

`lambda/lambda_function.py` を変更したら、ZIPを作り直してTerraformを適用する。

```bash
cd lambda
zip -r dist/lambda_function.zip lambda_function.py
cd ../terraform
terraform plan
terraform apply
```

`terraform/main.tf` では `source_code_hash` を使っているため、ZIP内容の変更はTerraform差分として検知される。

## トラブルシュート

### Unknown output type: JSON

AWS CLI の output 設定を小文字にする。

```bash
aws configure set output json
unset AWS_DEFAULT_OUTPUT
```

### Bedrock use case details

Anthropic初回利用時に以下が出る場合がある。

```text
Model use case details have not been submitted for this account.
```

Amazon Bedrock の Model catalog / Playground から Anthropic use case details を提出し、数分待ってから再実行する。

### AWS Marketplace権限

以下が出る場合は、初回有効化に Marketplace 権限が不足している。

```text
aws-marketplace:ViewSubscriptions
aws-marketplace:Subscribe
```

IAMユーザーに一時的に必要権限を付与し、Bedrock単体呼び出しで有効化する。

### outputs が空

まず中間出力を確認する。

```bash
aws s3 ls s3://drawio-kato-artifacts/tasks/<task_id>/ --recursive
```

`bedrock_text.txt` がある場合は Bedrock までは成功している。
DynamoDB の `error_message` を確認する。

### JSONDecodeError

Claudeの出力JSONが途中で切れた可能性がある。
現在のLambdaはフォールバックとして、生テキストを `design.md` に保存し、最小の `architecture.drawio` と `artifact.json` を出力する。

## 後片付け

PoC環境を削除する場合:

```bash
cd terraform
terraform destroy
```

S3バケットにオブジェクトが残っていると削除に失敗する場合がある。
必要な成果物を退避してから削除する。

## コスト管理

S3成果物にはライフサイクルを設定する。

```text
tasks/    30日で削除
logs/     30日で削除
outputs/  90日で削除
prompts/  90日で削除
```

保持期間を変える場合は Terraform 変数を上書きする。

```hcl
tasks_retention_days   = 30
logs_retention_days    = 30
outputs_retention_days = 90
prompts_retention_days = 90
```
