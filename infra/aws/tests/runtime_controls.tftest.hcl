# Every run is a mock plan. No provider credentials or real infrastructure.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}

variables {
  deploy_api            = true
  lambda_zip            = "tests/fixtures/plan-only-package.txt"
  runtime_enabled       = false
  manage_media_bucket   = true
  manage_execution_role = true
  allowed_account_ids   = ["011154879765"]
}

run "legacy_paused" {
  command = plan
  assert {
    condition = (
      alltrue([for f in aws_lambda_function.zip : f.reserved_concurrent_executions == 0]) &&
      aws_apigatewayv2_api.app[0].disable_execute_api_endpoint &&
      aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      alltrue([for m in aws_lambda_event_source_mapping.zip_queues : !m.enabled && length(m.scaling_config) == 0]) &&
      alltrue([for r in aws_cloudwatch_event_rule.maintenance : r.state == "DISABLED"]) &&
      length(aws_s3_bucket_notification.uploads) == 0 && !output.processing_enabled &&
      length(jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement) == 2
    )
    error_message = "Null controls must preserve every existing paused boundary."
  }
}

run "legacy_enabled_without_bindings" {
  command = plan
  variables { runtime_enabled = true }
  assert {
    condition = (
      alltrue([for f in aws_lambda_function.zip : f.reserved_concurrent_executions == -1]) &&
      !aws_apigatewayv2_api.app[0].disable_execute_api_endpoint &&
      !aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      aws_lambda_event_source_mapping.zip_queues["delete"].enabled &&
      aws_lambda_event_source_mapping.zip_queues["notify"].enabled &&
      !aws_lambda_event_source_mapping.zip_queues["infer"].enabled &&
      alltrue([for m in aws_lambda_event_source_mapping.zip_queues : length(m.scaling_config) == 1]) &&
      alltrue([for r in aws_cloudwatch_event_rule.maintenance : r.state == "ENABLED"]) &&
      length(aws_s3_bucket_notification.uploads) == 0 && !output.processing_enabled &&
      length(jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement) == 1
    )
    error_message = "Null controls must preserve legacy live behavior, including its disabled inference mapping's existing scaling block."
  }
}

run "legacy_ready" {
  command = plan
  variables {
    runtime_enabled      = true
    worker_image         = "example.invalid/mock-only@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url        = "https://example.invalid"
    google_invoker_email = "mock@example.invalid"
  }
  assert {
    condition = (
      aws_lambda_function.ingest[0].reserved_concurrent_executions == -1 &&
      aws_lambda_event_source_mapping.ingest[0].enabled &&
      length(aws_lambda_event_source_mapping.ingest[0].scaling_config) == 1 &&
      aws_lambda_event_source_mapping.zip_queues["infer"].enabled &&
      length(aws_s3_bucket_notification.uploads) == 1 &&
      length(aws_s3_bucket_notification.uploads[0].queue) == 1 && output.processing_enabled
    )
    error_message = "Null controls must retain legacy processing and upload destinations when all bindings exist."
  }
}

run "independent_manual_controls" {
  command = plan
  variables {
    worker_image                = "example.invalid/mock-only@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url               = "https://example.invalid"
    google_invoker_email        = "mock@example.invalid"
    manage_upload_notifications = false
    runtime_controls = {
      function_concurrency = { api = 1, ingest = 1, infer = 1, outbox = 1, delete = 1, cleanup = 1 }
      media_data_enabled   = true
    }
  }
  assert {
    condition = (
      aws_lambda_function.zip["api"].reserved_concurrent_executions == 1 &&
      aws_lambda_function.zip["notify"].reserved_concurrent_executions == 0 &&
      aws_lambda_function.zip["lex_fulfillment"].reserved_concurrent_executions == 0 &&
      aws_lambda_function.ingest[0].reserved_concurrent_executions == 1 &&
      aws_apigatewayv2_api.app[0].disable_execute_api_endpoint &&
      aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      alltrue([for m in aws_lambda_event_source_mapping.zip_queues : !m.enabled && length(m.scaling_config) == 0]) &&
      !aws_lambda_event_source_mapping.ingest[0].enabled && length(aws_lambda_event_source_mapping.ingest[0].scaling_config) == 0 &&
      alltrue([for r in aws_cloudwatch_event_rule.maintenance : r.state == "DISABLED"]) &&
      length(aws_s3_bucket_notification.uploads) == 0 && !output.processing_enabled &&
      length(jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement) == 1 &&
      alltrue([for f in aws_lambda_function.zip : f.runtime == "python3.12" && f.architectures == tolist(["x86_64"])]) &&
      length(aws_lambda_function.zip) == 7 && aws_lambda_function.ingest[0].package_type == "Image"
    )
    error_message = "Manual access must be independent from every automatic/public gate and preserve seven ZIP functions plus separate ingest."
  }
}

run "managed_notification_pause_retains_resource" {
  command = plan
  variables {
    manage_upload_notifications = true
    runtime_controls            = {}
  }
  assert {
    condition = (
      length(aws_s3_bucket_notification.uploads) == 1 && length(aws_s3_bucket_notification.uploads[0].queue) == 0
    )
    error_message = "Pausing destinations must retain an already managed notification resource even without processing bindings."
  }
}

run "explicit_automation_is_independent" {
  command = plan
  variables {
    manage_upload_notifications = false
    runtime_controls = {
      function_concurrency = { api = 1, delete = 2, outbox = 1 }
      api_endpoint_enabled = true
      queue_consumers      = ["delete"]
      schedules            = ["outbox"]
    }
  }
  assert {
    condition = (
      !aws_apigatewayv2_api.app[0].disable_execute_api_endpoint &&
      aws_cognito_user_pool.users.admin_create_user_config[0].allow_admin_create_user_only &&
      aws_lambda_event_source_mapping.zip_queues["delete"].enabled &&
      aws_lambda_event_source_mapping.zip_queues["delete"].scaling_config[0].maximum_concurrency == 2 &&
      !aws_lambda_event_source_mapping.zip_queues["notify"].enabled &&
      length(aws_lambda_event_source_mapping.zip_queues["notify"].scaling_config) == 0 &&
      aws_cloudwatch_event_rule.maintenance["outbox"].state == "ENABLED" &&
      aws_cloudwatch_event_rule.maintenance["cleanup"].state == "DISABLED" &&
      length(jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement) == 2
    )
    error_message = "Shared explicit controls must change only the selected endpoint, mapping and schedule."
  }
}

run "reject_global_enable_with_controls" {
  command = plan
  variables {
    runtime_enabled  = true
    runtime_controls = {}
  }
  expect_failures = [var.runtime_controls]
}
run "reject_unbounded_reservation" {
  command = plan
  variables { runtime_controls = { function_concurrency = { api = -1 } } }
  expect_failures = [var.runtime_controls]
}
run "reject_unknown_function" {
  command = plan
  variables { runtime_controls = { function_concurrency = { typo = 1 } } }
  expect_failures = [var.runtime_controls]
}
run "reject_fractional_reservation" {
  command = plan
  variables { runtime_controls = { function_concurrency = { api = 1.5 } } }
  expect_failures = [var.runtime_controls]
}
run "reject_consumer_above_reservation" {
  command = plan
  variables { runtime_controls = { function_concurrency = { delete = 1 }, queue_consumers = ["delete"] } }
  expect_failures = [var.runtime_controls]
}
run "reject_unknown_consumer" {
  command = plan
  variables { runtime_controls = { queue_consumers = ["api"] } }
  expect_failures = [var.runtime_controls]
}
run "reject_schedule_without_reservation" {
  command = plan
  variables { runtime_controls = { schedules = ["outbox"] } }
  expect_failures = [var.runtime_controls]
}
run "reject_missing_ingest_function" {
  command = plan
  variables { runtime_controls = { function_concurrency = { ingest = 1 } } }
  expect_failures = [var.runtime_controls]
}
run "reject_unmanaged_destination" {
  command = plan
  variables {
    worker_image                = "example.invalid/mock-only@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url               = "https://example.invalid"
    google_invoker_email        = "mock@example.invalid"
    manage_upload_notifications = false
    runtime_controls            = { upload_notifications_enabled = true }
  }
  expect_failures = [var.runtime_controls]
}
