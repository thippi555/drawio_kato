output "api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "task_table" {
  value = aws_dynamodb_table.tasks.name
}
