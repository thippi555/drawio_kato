# AIエージェント基盤 基本設計書 v0.1

## 1. システム概要

本システムは AWS Bedrock を利用し、AIエージェントによって各種タスクを実行する基盤である。

AI に対して自然言語でタスクを依頼し、設計書、構成図、Markdown、draw.io ファイルなどの成果物を生成する。

個人利用を前提とし、低コスト・サーバレス・小規模構成を基本方針とする。

---

## 2. システム目的

以下を目的として構築する。

- AIエージェントによるタスク自動化
- 設計書や構成図の自動生成
- Markdownベースの成果物管理
- draw.io によるアーキテクチャ図生成
- GitHub による成果物バージョン管理
- 将来的な AgentCore 対応

---

## 3. システム構成

### 3.1 全体構成

```text
利用者
  ↓
Web UI / CLI
  ↓
API Gateway
  ↓
Lambda
  ↓
Step Functions
  ↓
Amazon Bedrock (Claude)
  ↓
S3 / DynamoDB
  ↓
GitHub
```

---

## 4. 使用サービス

| 区分 | サービス | 用途 |
|---|---|---|
| AI基盤 | Amazon Bedrock | LLM実行 |
| モデル | Claude | 設計書・構成図生成 |
| 実行基盤 | AWS Lambda | タスク処理 |
| ワークフロー | Step Functions | タスク制御 |
| ストレージ | Amazon S3 | 成果物保存 |
| 状態管理 | DynamoDB | タスク管理 |
| API | API Gateway | 外部受付 |
| ソース管理 | GitHub | ドキュメント管理 |
| 将来拡張 | AgentCore Runtime | AIエージェント実行 |

---

## 5. 基本方針

### 5.1 低コスト方針

常時起動サーバーは利用しない。

以下のサーバレスサービスを中心とする。

- Lambda
- Step Functions
- Bedrock
- S3
- DynamoDB

---

### 5.2 拡張性方針

初期段階では最小構成とし、将来的に以下へ拡張可能とする。

- Bedrock Knowledge Bases
- RAG構成
- AgentCore Runtime
- Web UI
- Slack連携
- Teams連携

---

## 6. 想定タスク

### 6.1 設計書生成

入力例：

```text
Lambda + Bedrock + S3 の構成図を作成してください
```

出力：

- Markdown
- draw.io XML
- PNG
- JSON

---

### 6.2 構成図生成

AWS構成を draw.io 形式で生成する。

---

### 6.3 ドキュメント整理

生成した成果物を GitHub に保存する。

---

## 7. データ保存構成

### 7.1 S3構成

```text
s3://drawio-kato/
 ├── tasks/
 ├── outputs/
 ├── prompts/
 └── logs/
```

---

### 7.2 GitHub構成

```text
drawio_kato/
 ├── docs/
 ├── architecture/
 ├── prompts/
 ├── lambda/
 ├── terraform/
 └── samples/
```

---

## 8. タスク処理概要

### 8.1 処理フロー

1. ユーザーがタスク投入
2. API Gateway が受付
3. Lambda が Step Functions 起動
4. Bedrock が推論実施
5. 成果物を S3 保存
6. GitHub に反映
7. DynamoDB に状態保存

---

## 9. セキュリティ方針

- IAM最小権限
- Secrets Manager による秘密情報管理
- GitHub Token の安全管理
- Public S3 禁止
- CloudWatch Logs による監査

---

## 10. 今後の拡張予定

- AgentCore Runtime 統合
- Bedrock Knowledge Bases
- RAG対応
- 音声入力
- MCP Server連携
- マルチエージェント化
- 自動レビュー機能

---

## 11. 開発方針

- Markdownベース管理
- GitHub管理
- IaC管理
- 小規模PoCから段階的拡張
- 生成AI活用前提

