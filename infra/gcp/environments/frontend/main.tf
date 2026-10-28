terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "7.46.1" }
  }
  backend "local" {
    path = "state/frontend.tfstate"
  }
}

provider "google" {
  project = "ecoguard-fit3184-a2-2026"
  region  = "us-central1"
}

variable "frontend_image" {
  type        = string
  description = "Required reviewed immutable image; no mutable tag or empty default."
  validation {
    condition = can(regex(
      "^us-central1-docker\\.pkg\\.dev/ecoguard-fit3184-a2-2026/ecoguard/frontend@sha256:[0-9a-f]{64}$",
      var.frontend_image
    ))
    error_message = "Use this project's ecoguard/frontend image pinned by its reviewed SHA-256 digest."
  }
}

data "google_project" "current" {
  project_id = "ecoguard-fit3184-a2-2026"
}

resource "google_service_account" "frontend" {
  project      = "ecoguard-fit3184-a2-2026"
  account_id   = "ecoguard-frontend"
  display_name = "EcoGuard static frontend, no assigned project roles"
  lifecycle {
    precondition {
      condition     = tostring(data.google_project.current.number) == "995070689587"
      error_message = "Stop: unexpected GCP project identity."
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  project              = "ecoguard-fit3184-a2-2026"
  location             = "us-central1"
  name                 = "ecoguard-web"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  scaling {
    min_instance_count    = 0
    max_instance_count    = 1
    scaling_mode          = "AUTOMATIC"
    manual_instance_count = 0
  }
  template {
    service_account                  = "${google_service_account.frontend.account_id}@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com"
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "30s"
    max_instance_request_concurrency = 80
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.frontend_image
      ports {
        name           = "http1"
        container_port = 8080
      }
      resources {
        limits            = { cpu = "1", memory = "256Mi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      startup_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 0
        timeout_seconds       = 1
        period_seconds        = 3
        failure_threshold     = 10
      }
    }
  }
}

# Public access is to static assets only. Private inference IAM is not managed here.
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = "ecoguard-fit3184-a2-2026"
  location = "us-central1"
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "frontend_url" {
  value = google_cloud_run_v2_service.frontend.uri
}
