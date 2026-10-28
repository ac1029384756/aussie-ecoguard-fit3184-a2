mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "995070689587" }
  }
}

variables {
  frontend_image = "us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000"
}

run "bounded_static_frontend" {
  command = plan
  assert {
    condition = (
      google_cloud_run_v2_service.frontend.name == "ecoguard-web" &&
      google_cloud_run_v2_service.frontend.invoker_iam_disabled == false &&
      google_cloud_run_v2_service.frontend.template[0].service_account == "ecoguard-frontend@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com" &&
      google_cloud_run_v2_service_iam_member.frontend_public.name == "ecoguard-web" &&
      google_cloud_run_v2_service_iam_member.frontend_public.role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.frontend_public.member == "allUsers"
    )
    error_message = "The public grant must target only the static frontend with its dedicated runtime identity."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.frontend.scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.frontend.scaling[0].max_instance_count == 1 &&
      google_cloud_run_v2_service.frontend.template[0].scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.frontend.template[0].scaling[0].max_instance_count == 1 &&
      google_cloud_run_v2_service.frontend.template[0].containers[0].resources[0].limits["cpu"] == "1" &&
      google_cloud_run_v2_service.frontend.template[0].containers[0].resources[0].limits["memory"] == "256Mi" &&
      google_cloud_run_v2_service.frontend.template[0].containers[0].resources[0].cpu_idle == true &&
      google_cloud_run_v2_service.frontend.template[0].containers[0].resources[0].startup_cpu_boost == false
    )
    error_message = "Frontend request-based billing and both min0/max1 limits must be retained."
  }
}

run "reject_mutable_image" {
  command = plan
  variables {
    frontend_image = "us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/frontend:latest"
  }
  expect_failures = [var.frontend_image]
}

run "reject_inference_image" {
  command = plan
  variables {
    frontend_image = "us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  expect_failures = [var.frontend_image]
}

run "reject_other_project_image" {
  command = plan
  variables {
    frontend_image = "us-central1-docker.pkg.dev/other-project/ecoguard/frontend@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
  expect_failures = [var.frontend_image]
}

run "reject_wrong_project_identity" {
  command = plan
  override_data {
    target = data.google_project.current
    values = { number = "111111111111" }
  }
  expect_failures = [google_service_account.frontend]
}
