# Supply -var=lambda_zip=/absolute/path/to/the/unchanged/reviewed.zip.
# These are mock plans only. The synthetic URI is never used to pull an image.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}

run "foundation_paused" {
  command = plan
  assert {
    condition = (
      output.deployment_stage == "foundation-paused" && !output.runtime_enabled && !output.processing_enabled &&
      alltrue([for n in output.runtime_controls.function_concurrency : n == 0]) &&
      !output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && !output.runtime_controls.manages_upload_notifications &&
      length(output.runtime_controls.queue_consumers) == 0 && length(output.runtime_controls.schedules) == 0
    )
    error_message = "The default personal stage must retain all foundation pause boundaries."
  }
}

run "wiring_paused" {
  command = plan
  variables {
    deployment_stage = "wiring-paused"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  assert {
    condition = (
      !output.runtime_enabled && !output.processing_enabled &&
      alltrue([for n in output.runtime_controls.function_concurrency : n == 0]) &&
      !output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && !output.runtime_controls.manages_upload_notifications &&
      !output.runtime_controls.upload_notifications_enabled &&
      length(output.runtime_controls.queue_consumers) == 0 && length(output.runtime_controls.schedules) == 0
    )
    error_message = "Adding wiring must not activate any runtime/public/automatic control."
  }
}

run "auth_smoke" {
  command = plan
  variables {
    deployment_stage = "auth-smoke"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  assert {
    condition = (
      !output.runtime_enabled && !output.processing_enabled &&
      output.runtime_controls.function_concurrency.api == 1 &&
      alltrue([for name, n in output.runtime_controls.function_concurrency : n == (name == "api" ? 1 : 0)]) &&
      !output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && !output.runtime_controls.manages_upload_notifications &&
      length(output.runtime_controls.queue_consumers) == 0 && length(output.runtime_controls.schedules) == 0
    )
    error_message = "Auth smoke must reserve exactly the API function while keeping media and all entry points/automation paused."
  }
}

run "media_manual" {
  command = plan
  variables {
    deployment_stage = "media-manual"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  assert {
    condition = (
      !output.runtime_enabled && !output.processing_enabled &&
      alltrue([for name, n in output.runtime_controls.function_concurrency : n == (contains(["api", "ingest", "infer", "outbox", "delete", "cleanup"], name) ? 1 : 0)]) &&
      output.runtime_controls.media_data_enabled && !output.runtime_controls.api_endpoint_enabled &&
      !output.runtime_controls.public_signup_enabled && !output.runtime_controls.manages_upload_notifications &&
      length(output.runtime_controls.queue_consumers) == 0 && length(output.runtime_controls.schedules) == 0
    )
    error_message = "Manual media must reserve exactly six selected functions and enable only private data access."
  }
}

run "reject_unknown_stage" {
  command = plan
  variables {
    deployment_stage = "live"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  expect_failures = [var.deployment_stage]
}
run "reject_wiring_without_image" {
  command = plan
  variables {
    deployment_stage = "wiring-paused"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  expect_failures = [var.worker_image]
}
run "reject_mutable_tag" {
  command = plan
  variables {
    deployment_stage = "wiring-paused"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker:reviewed"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  expect_failures = [var.worker_image]
}
run "reject_other_repository" {
  command = plan
  variables {
    deployment_stage = "wiring-paused"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/other-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
  }
  expect_failures = [var.worker_image]
}
run "reject_other_run_service" {
  command = plan
  variables {
    deployment_stage = "auth-smoke"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://other-service-adlnb7yumq-uc.a.run.app"
  }
  expect_failures = [var.inference_url]
}
run "reject_audience_trailing_slash" {
  command = plan
  variables {
    deployment_stage = "auth-smoke"
    worker_image     = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    inference_url    = "https://ecoguard-inference-adlnb7yumq-uc.a.run.app/"
  }
  expect_failures = [var.inference_url]
}
run "reject_image_removal_disguised_as_foundation" {
  command = plan
  variables {
    worker_image = "011154879765.dkr.ecr.us-east-1.amazonaws.com/ecoguard3184-personal-worker@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  expect_failures = [var.worker_image]
}
run "reject_changed_package" {
  command = plan
  variables {
    lambda_zip = abspath("tests/fixtures/hash-mismatch.zip")
  }
  expect_failures = [var.lambda_zip]
}
