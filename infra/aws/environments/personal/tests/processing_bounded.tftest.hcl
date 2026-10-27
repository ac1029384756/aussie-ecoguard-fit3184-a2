# Additional source-only mock plans. Supply the same unchanged reviewed ZIP.
# These tests do not prove a real 59->60 diff, event delivery or a stop timer.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}

variables {
  worker_image  = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  inference_url = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
}

run "processing_exact_selected_automatic_controls" {
  command = plan
  variables {
    deployment_stage           = "processing-bounded"
    adopt_upload_notifications = true
  }
  assert {
    condition = (
      !output.runtime_enabled && output.processing_enabled &&
      alltrue([for name, n in output.runtime_controls.function_concurrency : n == lookup({ ingest = -1, infer = -1, outbox = -1 }, name, 0)]) &&
      output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && output.runtime_controls.manages_upload_notifications &&
      output.runtime_controls.upload_notifications_enabled &&
      output.runtime_controls.queue_consumers == toset(["ingest", "infer"]) &&
      output.runtime_controls.schedules == toset(["outbox"])
    )
    error_message = "Only unreserved ingest/infer/outbox, the two consumers, outbox schedule and adopted incoming notification may activate."
  }
}

run "adopted_wiring_pause_retains_owner_without_destinations" {
  command = plan
  variables {
    deployment_stage           = "wiring-paused"
    adopt_upload_notifications = true
  }
  assert {
    condition = (
      !output.runtime_enabled && !output.processing_enabled &&
      alltrue([for n in output.runtime_controls.function_concurrency : n == 0]) &&
      !output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && output.runtime_controls.manages_upload_notifications &&
      !output.runtime_controls.upload_notifications_enabled &&
      length(output.runtime_controls.queue_consumers) == 0 && length(output.runtime_controls.schedules) == 0
    )
    error_message = "Adopted pause must retain notification ownership while disabling data and every destination/runtime entry."
  }
}

run "reject_processing_without_notification_adoption" {
  command = plan
  variables {
    deployment_stage           = "processing-bounded"
    adopt_upload_notifications = false
  }
  expect_failures = [var.adopt_upload_notifications]
}

run "reject_foundation_for_adopted_environment" {
  command = plan
  variables {
    deployment_stage           = "foundation-paused"
    adopt_upload_notifications = true
    worker_image               = ""
    inference_url              = ""
  }
  expect_failures = [var.adopt_upload_notifications]
}
