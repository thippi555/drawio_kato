# AIエージェント基盤 機能一覧 v0.1

## 1. 概要

本書は AIエージェント基盤における機能一覧を定義する。

---

# 2. 機能一覧

| 機能ID | 機能名 | 概要 | 実行サービス |
|---|---|---|---|
| F-001 | タスク登録 | ユーザーからタスクを受付 | API Gateway / Lambda |
| F-002 | タスク実行 | AIエージェントによる処理実行 | Lambda / Bedrock |
| F-003 | ワークフロー制御 | タスク順序制御 | Step Functions |
| F-004 | AI推論実行 | Claudeによる推論処理 | Bedrock |
| F-005 | 設計書生成 | Markdown設計書生成 | Bedrock |
| F-006 | draw.io生成 | draw.io XML生成 | Bedrock / Lambda |
| F-007 | 成果物保存 | S3への保存 | S3 |
| F-008 | タスク状態管理 | ステータス管理 | DynamoDB |
| F-009 | GitHub連携 | GitHubへ成果物反映 | Lambda |
| F-010 | ログ出力 | CloudWatch Logs出力 | CloudWatch |
| F-011 | エラー管理 | 失敗時制御 | Step Functions |
| F-012 | プロンプト管理 | AIプロンプト管理 | S3 / GitHub |
| F-013 | 認証制御 | APIアクセス制御 | IAM / API Gateway |
| F-014 | 構成図生成 | AWS構成図生成 | Bedrock |
| F-015 | JSON生成 | 中間構造生成 | Lambda |
| F-016 | ファイル出力 | Markdown / JSON 出力 | Lambda |
| F-017 | 実行履歴管理 | タスク履歴保存 | DynamoDB |
| F-018 | Agent実行基盤 | AgentCore実行 | AgentCore Runtime |
| F-019 | ナレッジ検索 | RAG検索 | Knowledge Bases |
| F-020 | Git管理 | ドキュメント版管理 | GitHub |

---

# 3. タスク登録機能

## 3.1 概要

ユーザーから自然言語でタスクを受付する。

---

## 3.2 入力例

```text
AWS構成図を生成してください
```

---

## 3.3 出力

| 項目 | 内容 |
|---|---|
| task_id | タスクID |
| status | ACCEPTED |
| request_time | 受付時刻 |

---

# 4. AI推論機能

## 4.1 概要

Amazon Bedrock Claude を利用し、タスク内容を解析する。

---

## 4.2 処理内容

- 自然言語解析
- 構成分析
- draw.io生成
- Markdown生成
- JSON生成

---

# 5. draw.io生成機能

## 5.1 概要

AWS構成を draw.io XML として生成する。

---

## 5.2 入力

```json
{
  "services": [
    "Lambda",
    "Bedrock",
    "S3"
  ]
}
```

---

## 5.3 出力

```text
architecture.drawio
```

---

# 6. 成果物保存機能

## 6.1 概要

生成した成果物を S3 に保存する。

---

## 6.2 保存対象

- Markdown
- draw.io
- JSON
- PNG
- ログ

---

# 7. GitHub連携機能

## 7.1 概要

生成成果物を GitHub リポジトリへ保存する。

---

## 7.2 保存対象

```text
/docs
/architecture
/prompts
/samples
```

---

# 8. タスク状態管理機能

## 8.1 概要

タスク実行状態を DynamoDB で管理する。

---

## 8.2 管理項目

| 項目 | 内容 |
|---|---|
| task_id | タスクID |
| status | 実行状態 |
| start_time | 開始時刻 |
| end_time | 終了時刻 |
| output_path | 出力先 |
| error_message | エラー内容 |

---

# 9. エラー制御機能

## 9.1 概要

タスク失敗時の制御を実施する。

---

## 9.2 対応内容

- リトライ
- エラーログ保存
- CloudWatch出力
- 異常終了管理

---

# 10. 将来拡張機能

## 10.1 RAG対応

Knowledge Bases を利用した社内文書検索。

---

## 10.2 AgentCore対応

複数エージェント実行対応。

---

## 10.3 音声対応

音声入力によるタスク実行。

---

## 10.4 MCP Server連携

外部ツール連携対応。

```
