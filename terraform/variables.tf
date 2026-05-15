variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}

variable "project_name" {
  type    = string
  default = "drawio-kato"
}

variable "artifact_bucket_name" {
  type    = string
  default = "drawio-kato-artifacts"
}

variable "bedrock_model_id" {
  type    = string
  default = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "github_owner" {
  type    = string
  default = "thippi555"
}

variable "github_repo" {
  type    = string
  default = "drawio_kato"
}

variable "github_branch" {
  type    = string
  default = "main"
}

variable "github_token_secret_id" {
  type    = string
  default = ""
}

variable "lambda_zip_path" {
  type    = string
  default = "../lambda/dist/lambda_function.zip"
}

variable "tasks_retention_days" {
  type    = number
  default = 30
}

variable "logs_retention_days" {
  type    = number
  default = 30
}

variable "outputs_retention_days" {
  type    = number
  default = 90
}

variable "prompts_retention_days" {
  type    = number
  default = 90
}
