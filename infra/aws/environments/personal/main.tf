terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.0, < 7.0" }
  }
  # Relative to THIS root, never infra/aws or the course deployment's state.
  backend "local" {
    path = "state/terraform.tfstate"
  }
}

variable "lambda_zip" {
  type        = string
  description = "Absolute POSIX path to the real, reviewed Linux Python 3.12 Lambda ZIP; no default or placeholder archive."
  validation {
    condition     = startswith(var.lambda_zip, "/") && endswith(var.lambda_zip, ".zip") && fileexists(var.lambda_zip)
    error_message = "Supply an existing real .zip via its absolute POSIX path. Build and review the actual Lambda package first."
  }
  validation {
    condition     = try(filesha256(var.lambda_zip) == "fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6", false)
    error_message = "Every draft stage requires the unchanged reviewed seven-function ZIP (SHA-256 fafb94bf948312f1fef8998b5619567ad3c3471381a34e9e816cec87b034d9f6). A package change needs separate review."
  }
}

variable "deployment_stage" {
  type        = string
  description = "Reviewed fixed stage. processing-bounded needs separate activation review and a bounded pause controller. After wiring/adoption, pause with wiring-paused and retain adoption."
  default     = "foundation-paused"
  nullable    = false
  validation {
    condition     = contains(["foundation-paused", "wiring-paused", "auth-smoke", "media-manual", "processing-bounded"], var.deployment_stage)
    error_message = "Choose foundation-paused, wiring-paused, auth-smoke, media-manual or processing-bounded."
  }
}

# Once created, keep this true when pausing: empty destinations, not destruction.
variable "adopt_upload_notifications" {
  type        = bool
  description = "Explicit sole-bucket notification ownership. Default false; processing requires true. Once adopted, retain true with wiring-paused."
  default     = false
  nullable    = false
  validation {
    condition = var.deployment_stage == "processing-bounded" ? var.adopt_upload_notifications : !(
      var.adopt_upload_notifications && var.deployment_stage == "foundation-paused"
    )
    error_message = "Processing requires notification adoption; an adopted environment must pause with wiring-paused, never foundation-paused."
  }
}

variable "worker_image" {
  type        = string
  description = "Independently verified published ECR manifest URI. Syntax alone does not prove publication, architecture or provenance."
  default     = ""
  nullable    = false
  validation {
    condition = var.deployment_stage == "foundation-paused" ? var.worker_image == "" : can(regex(
      "^011154879765[.]dkr[.]ecr[.]us-east-1[.]amazonaws[.]com/ecoguard3184-personal-worker@sha256:[0-9a-f]{64}$",
      var.worker_image
    ))
    error_message = "Foundation requires an empty image; other stages require the exact personal ECR repository with a verified published sha256 digest, never a tag or local image ID."
  }
}

variable "inference_url" {
  type        = string
  description = "Fixed private Run base URL; CloudRunClient also uses this exact string as its token audience. Reverify the service identity before a real plan."
  default     = ""
  nullable    = false
  validation {
    condition = var.deployment_stage == "foundation-paused" ? var.inference_url == "" : (
      var.inference_url == "https://ecoguard-inference-adlnb7yumq-uc.a.run.app"
    )
    error_message = "Foundation requires an empty URL; other stages require exactly https://ecoguard-inference-adlnb7yumq-uc.a.run.app without a trailing slash, path or query."
  }
}

locals {
  stage_reservations = {
    foundation-paused  = {}
    wiring-paused      = {}
    auth-smoke         = { api = 1 }
    media-manual       = { api = 1, ingest = 1, infer = 1, outbox = 1, delete = 1, cleanup = 1 }
    processing-bounded = { ingest = -1, infer = -1, outbox = -1 }
  }
  runtime_controls = {
    function_concurrency         = lookup(local.stage_reservations, var.deployment_stage, {})
    media_data_enabled           = contains(["media-manual", "processing-bounded"], var.deployment_stage)
    api_endpoint_enabled         = false
    public_signup_enabled        = false
    queue_consumers              = var.deployment_stage == "processing-bounded" ? ["ingest", "infer"] : []
    schedules                    = var.deployment_stage == "processing-bounded" ? ["outbox"] : []
    upload_notifications_enabled = var.deployment_stage == "processing-bounded"
  }
}

# infra/aws contains its own provider. This legacy-provider module must remain
# a single unconditional call: no count, for_each, depends_on or provider alias.
# Child modules do not load deployment.auto.tfvars from the child's directory.
module "ecoguard" {
  source = "../.."

  allowed_account_ids                   = ["011154879765"]
  region                                = "us-east-1"
  prefix                                = "ecoguard3184"
  environment                           = "personal"
  manage_media_bucket                   = true
  manage_execution_role                 = true
  execution_role_arn                    = ""
  deploy_api                            = true
  runtime_enabled                       = false
  runtime_controls                      = local.runtime_controls
  allow_unreserved_processing_functions = var.deployment_stage == "processing-bounded"
  manage_upload_notifications           = var.adopt_upload_notifications
  lambda_zip                            = var.lambda_zip

  model_manifest_version        = "ecoguard-models-2026-10-08-v3"
  frontend_origins              = ["http://localhost:5173", "http://127.0.0.1:5173"]
  web_url                       = "http://127.0.0.1:5173"
  worker_image                  = var.worker_image
  manage_ingest_ecr_pull_policy = var.deployment_stage != "foundation-paused"
  inference_url                 = var.inference_url
  google_invoker_email          = var.deployment_stage == "foundation-paused" ? "" : "ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com"
  lex_bot_id                    = ""
  lex_alias_id                  = ""

  # Prepared access change only: requires review/approval before deployment.
  allow_root_bucket_inventory_while_paused = true
}

output "deployment_identity" {
  value = { account_id = module.ecoguard.account_id, region = module.ecoguard.region }
}
output "execution_role_arn" { value = module.ecoguard.execution_role_arn }
output "media_bucket" { value = module.ecoguard.media_bucket }
output "api_url" { value = module.ecoguard.api_url }
output "cognito_user_pool_id" { value = module.ecoguard.cognito_user_pool_id }
output "cognito_client_id" { value = module.ecoguard.cognito_client_id }
output "worker_repository_url" { value = module.ecoguard.worker_repository_url }
output "runtime_enabled" { value = module.ecoguard.runtime_enabled }
output "processing_enabled" { value = module.ecoguard.processing_enabled }
output "deployment_stage" { value = var.deployment_stage }
output "runtime_controls" { value = module.ecoguard.runtime_controls }
