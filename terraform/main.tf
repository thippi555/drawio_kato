terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

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

resource "aws_s3_bucket" "artifacts" {
  bucket = var.artifact_bucket_name
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-tasks"
    status = "Enabled"

    filter {
      prefix = "tasks/"
    }

    expiration {
      days = var.tasks_retention_days
    }
  }

  rule {
    id     = "expire-logs"
    status = "Enabled"

    filter {
      prefix = "logs/"
    }

    expiration {
      days = var.logs_retention_days
    }
  }

  rule {
    id     = "expire-outputs"
    status = "Enabled"

    filter {
      prefix = "outputs/"
    }

    expiration {
      days = var.outputs_retention_days
    }
  }

  rule {
    id     = "expire-prompts"
    status = "Enabled"

    filter {
      prefix = "prompts/"
    }

    expiration {
      days = var.prompts_retention_days
    }
  }
}

resource "aws_dynamodb_table" "tasks" {
  name         = "ai_agent_tasks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "task_id"

  attribute {
    name = "task_id"
    type = "S"
  }
}

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.tasks.arn
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.project_name}-task-flow"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.github_token_secret_id == "" ? "*" : "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.github_token_secret_id}*"
      }
    ]
  })
}

resource "aws_lambda_function" "task_processor" {
  function_name    = "${var.project_name}-task-processor"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  timeout          = 120
  memory_size      = 256

  environment {
    variables = {
      TASK_TABLE_NAME        = aws_dynamodb_table.tasks.name
      ARTIFACT_BUCKET        = aws_s3_bucket.artifacts.bucket
      STATE_MACHINE_ARN      = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.project_name}-task-flow"
      BEDROCK_MODEL_ID       = var.bedrock_model_id
      GITHUB_OWNER           = var.github_owner
      GITHUB_REPO            = var.github_repo
      GITHUB_BRANCH          = var.github_branch
      GITHUB_TOKEN_SECRET_ID = var.github_token_secret_id
    }
  }
}

resource "aws_iam_role" "stepfunctions" {
  name = "${var.project_name}-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "stepfunctions" {
  name = "${var.project_name}-stepfunctions-policy"
  role = aws_iam_role.stepfunctions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.task_processor.arn
    }]
  })
}

resource "aws_sfn_state_machine" "task_flow" {
  name     = "${var.project_name}-task-flow"
  role_arn = aws_iam_role.stepfunctions.arn

  definition = templatefile("${path.module}/../stepfunctions/task_flow.asl.json", {
    lambda_function_arn = aws_lambda_function.task_processor.arn
  })
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.task_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "task_post" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /tasks"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.task_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "task_table" {
  value = aws_dynamodb_table.tasks.name
}
