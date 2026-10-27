# New tests only: all mocked, no account/quota request or runtime activation.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}

variables {
  deploy_api                               = true
  lambda_zip                               = "tests/fixtures/plan-only-package.txt"
  runtime_enabled                          = false
  manage_media_bucket                      = true
  manage_execution_role                    = true
  allowed_account_ids                      = ["011154879765"]
  prefix                                   = "ecoguard3184"
  environment                              = "personal"
  worker_image                             = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  inference_url                            = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  google_invoker_email                     = "ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com"
  manage_upload_notifications              = true
  manage_ingest_ecr_pull_policy            = true
  allow_root_bucket_inventory_while_paused = true
  runtime_controls = {
    function_concurrency         = { ingest = -1, infer = -1, outbox = -1 }
    media_data_enabled           = true
    api_endpoint_enabled         = false
    public_signup_enabled        = false
    queue_consumers              = ["ingest", "infer"]
    schedules                    = ["outbox"]
    upload_notifications_enabled = true
  }
}

run "default_optin_false_still_rejects_explicit_unreserved" {
  command         = plan
  expect_failures = [var.runtime_controls]
}

run "exact_personal_unreserved_three_only_two_sqs_caps" {
  command = plan
  variables { allow_unreserved_processing_functions = true }
  assert {
    condition = (
      alltrue([for name, f in aws_lambda_function.zip : f.reserved_concurrent_executions == (contains(["infer", "outbox"], name) ? -1 : 0)]) &&
      aws_lambda_function.ingest[0].reserved_concurrent_executions == -1 &&
      aws_lambda_event_source_mapping.ingest[0].enabled && aws_lambda_event_source_mapping.ingest[0].scaling_config[0].maximum_concurrency == 2 &&
      aws_lambda_event_source_mapping.zip_queues["infer"].enabled && aws_lambda_event_source_mapping.zip_queues["infer"].scaling_config[0].maximum_concurrency == 2 &&
      !aws_lambda_event_source_mapping.zip_queues["notify"].enabled && !aws_lambda_event_source_mapping.zip_queues["delete"].enabled &&
      aws_cloudwatch_event_rule.maintenance["outbox"].state == "ENABLED" && aws_cloudwatch_event_rule.maintenance["cleanup"].state == "DISABLED" &&
      aws_apigatewayv2_api.app[0].disable_execute_api_endpoint && aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      length(aws_s3_bucket_notification.uploads[0].queue) == 1 && aws_s3_bucket_notification.uploads[0].queue[0].filter_prefix == "incoming/"
    )
    error_message = "Only the three exact unreserved functions and two SQS caps of two may run; no outbox reservation cap is asserted."
  }
}

run "optin_rejects_wrong_account_allowlist" {
  command = plan
  variables {
    allow_unreserved_processing_functions = true
    allowed_account_ids                   = ["999999999999"]
  }
  expect_failures = [var.runtime_controls]
}

run "optin_rejects_extra_api_reservation" {
  command = plan
  variables {
    allow_unreserved_processing_functions = true
    runtime_controls = {
      function_concurrency         = { ingest = -1, infer = -1, outbox = -1, api = 1 }
      media_data_enabled           = true
      queue_consumers              = ["ingest", "infer"]
      schedules                    = ["outbox"]
      upload_notifications_enabled = true
    }
  }
  expect_failures = [var.runtime_controls]
}

run "optin_rejects_notify_consumer" {
  command = plan
  variables {
    allow_unreserved_processing_functions = true
    runtime_controls = {
      function_concurrency         = { ingest = -1, infer = -1, outbox = -1 }
      media_data_enabled           = true
      queue_consumers              = ["ingest", "infer", "notify"]
      schedules                    = ["outbox"]
      upload_notifications_enabled = true
    }
  }
  expect_failures = [var.runtime_controls]
}

run "optin_rejects_cleanup_schedule" {
  command = plan
  variables {
    allow_unreserved_processing_functions = true
    runtime_controls = {
      function_concurrency         = { ingest = -1, infer = -1, outbox = -1 }
      media_data_enabled           = true
      queue_consumers              = ["ingest", "infer"]
      schedules                    = ["outbox", "cleanup"]
      upload_notifications_enabled = true
    }
  }
  expect_failures = [var.runtime_controls]
}

run "legacy_null_mode_keeps_historical_unreserved_without_optin" {
  command = plan
  variables {
    runtime_enabled  = true
    runtime_controls = null
  }
  assert {
    condition     = alltrue([for f in aws_lambda_function.zip : f.reserved_concurrent_executions == -1]) && aws_lambda_function.ingest[0].reserved_concurrent_executions == -1
    error_message = "Null legacy controls must retain their existing behavior while the new opt-in stays false."
  }
}

run "pause_all_zero_keeps_notification_owner_without_any_destination" {
  command = plan
  variables { runtime_controls = {} }
  assert {
    condition = (
      alltrue([for f in aws_lambda_function.zip : f.reserved_concurrent_executions == 0]) && aws_lambda_function.ingest[0].reserved_concurrent_executions == 0 &&
      !aws_lambda_event_source_mapping.ingest[0].enabled && length(aws_lambda_event_source_mapping.ingest[0].scaling_config) == 0 &&
      alltrue([for m in aws_lambda_event_source_mapping.zip_queues : !m.enabled && length(m.scaling_config) == 0]) &&
      alltrue([for r in aws_cloudwatch_event_rule.maintenance : r.state == "DISABLED"]) &&
      length(aws_s3_bucket_notification.uploads) == 1 && length(aws_s3_bucket_notification.uploads[0].queue) == 0
    )
    error_message = "Pause must put every function at zero and retain the empty notification resource, without any quota evidence requirement."
  }
}
