output "region" { value = var.region }
output "account_id" { value = data.aws_caller_identity.current.account_id }
output "execution_role_arn" { value = local.role_arn }
output "media_bucket" { value = local.bucket_name }
output "table_names" { value = { for k, t in aws_dynamodb_table.data : k => t.name } }
output "queue_urls" { value = { for k, q in aws_sqs_queue.work : k => q.url } }
output "queue_arns" { value = { for k, q in aws_sqs_queue.work : k => q.arn } }
output "outbox_stream_arn" { value = aws_dynamodb_table.data["outbox"].stream_arn }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.users.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "cognito_issuer" { value = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.users.id}" }
output "worker_repository_url" { value = aws_ecr_repository.worker.repository_url }
output "runtime_controls" {
  description = "Effective independent controls, including explicit legacy-mode values. Manual stages keep processing_enabled=false because automatic queue consumers are off."
  value = {
    explicit                     = local.controlled_runtime
    function_concurrency         = local.function_concurrency
    media_data_enabled           = local.media_data_enabled
    api_endpoint_enabled         = local.api_endpoint_enabled
    public_signup_enabled        = local.public_signup_enabled
    queue_consumers              = toset([for name, enabled in local.queue_consumers_enabled : name if enabled])
    schedules                    = toset([for name, enabled in local.schedules_enabled : name if enabled])
    manages_upload_notifications = local.manage_upload_notifications
    upload_notifications_enabled = local.manage_upload_notifications && local.upload_notifications_enabled
  }
}
