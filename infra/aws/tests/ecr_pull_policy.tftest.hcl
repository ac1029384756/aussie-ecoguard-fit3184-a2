# Mock provider plans only. No image is pulled and no caller credentials are used.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}
variables {
  region                      = "us-east-1"
  prefix                      = "ecoguard3184"
  environment                 = "personal"
  deploy_api                  = true
  lambda_zip                  = "tests/fixtures/plan-only-package.txt"
  runtime_enabled             = false
  runtime_controls            = {}
  manage_media_bucket         = true
  manage_execution_role       = true
  manage_upload_notifications = false
}
run "legacy_default_does_not_manage_policy" {
  command = plan
  variables {
    worker_image = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  assert {
    condition     = length(aws_ecr_repository_policy.lambda_ingest) == 0
    error_message = "The default must preserve legacy ECR policy ownership."
  }
}
run "opt_in_without_worker_has_no_policy" {
  command = plan
  variables { manage_ingest_ecr_pull_policy = true }
  assert {
    condition     = length(aws_ecr_repository_policy.lambda_ingest) == 0 && length(aws_lambda_function.ingest) == 0
    error_message = "No image/ingest means no new service pull policy."
  }
}
run "exact_ingest_pull_keeps_application_paused" {
  command = plan
  variables {
    manage_ingest_ecr_pull_policy = true
    worker_image                  = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  assert {
    condition = (
      length(aws_ecr_repository_policy.lambda_ingest) == 1 &&
      aws_ecr_repository_policy.lambda_ingest[0].repository == "ecoguard3184-personal-worker" &&
      jsondecode(aws_ecr_repository_policy.lambda_ingest[0].policy) == {
        Version = "2012-10-17"
        Statement = [{
          Sid       = "LambdaECRImageRetrievalPolicy", Effect = "Allow"
          Principal = { Service = "lambda.amazonaws.com" }
          Action    = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
          Resource  = "arn:aws:ecr:us-east-1:011154879765:repository/ecoguard3184-personal-worker"
          Condition = {
            ArnEquals    = { "aws:SourceArn" = "arn:aws:lambda:us-east-1:011154879765:function:ecoguard3184-personal-ingest" }
            StringEquals = { "aws:SourceAccount" = "011154879765" }
          }
        }]
      } &&
      aws_lambda_function.ingest[0].reserved_concurrent_executions == 0 &&
      alltrue([for f in aws_lambda_function.zip : f.reserved_concurrent_executions == 0]) &&
      aws_lambda_event_source_mapping.ingest[0].function_name == "arn:aws:lambda:us-east-1:011154879765:function:ecoguard3184-personal-ingest" &&
      !aws_lambda_event_source_mapping.ingest[0].enabled &&
      aws_apigatewayv2_api.app[0].disable_execute_api_endpoint &&
      aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      alltrue([for r in aws_cloudwatch_event_rule.maintenance : r.state == "DISABLED"]) &&
      length(aws_s3_bucket_notification.uploads) == 0 && !output.processing_enabled
    )
    error_message = "Only the exact ingest principal/function/repository read pair is permitted; every application boundary stays paused."
  }
}
run "reject_policy_outside_reviewed_region" {
  command = plan
  variables {
    manage_ingest_ecr_pull_policy = true
    region                        = "ap-southeast-2"
    worker_image                  = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  expect_failures = [aws_ecr_repository_policy.lambda_ingest[0]]
}
