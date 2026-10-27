variable "region" {
  type    = string
  default = "us-east-1"
}
variable "environment" {
  type    = string
  default = "dev"
}
variable "prefix" {
  type    = string
  default = "ecoguard3184"
}
variable "manage_media_bucket" {
  type        = bool
  description = "Opt in to a new Terraform-managed media bucket and BucketOwnerEnforced ownership. False preserves the course's externally bootstrapped bucket."
  default     = false
}
variable "allow_root_bucket_inventory_while_paused" {
  type        = bool
  nullable    = false
  description = "Opt in to exempt only this account's root user from the paused s3:ListBucket deny, for HeadBucket refresh and object-name inventory. Object access, version listing and multipart listing remain denied."
  default     = false
}
variable "frontend_origins" {
  type    = list(string)
  default = ["http://localhost:5173", "http://127.0.0.1:5173"]
}
variable "execution_role_arn" {
  type        = string
  description = "Existing execution role. Learner Lab normally permits LabRole; record its broader permissions."
  default     = ""
}
variable "manage_execution_role" {
  type        = bool
  description = "Opt in to a dedicated project Lambda role. False preserves the existing-role/LabRole behavior."
  default     = false
  validation {
    condition     = !var.manage_execution_role || var.execution_role_arn == ""
    error_message = "Choose either manage_execution_role=true or an existing execution_role_arn, not both."
  }
}
variable "allowed_account_ids" {
  type        = list(string)
  description = "AWS provider account allowlist. Empty preserves historical behavior; new environments must set an explicit account."
  default     = []
  validation {
    condition     = alltrue([for account in var.allowed_account_ids : can(regex("^[0-9]{12}$", account))])
    error_message = "Each allowed account ID must contain exactly 12 decimal digits."
  }
}
variable "deploy_api" {
  type    = bool
  default = false
}
variable "runtime_enabled" {
  type        = bool
  description = "Reversible runtime/access pause. Keep deploy_api and all existing resource inputs unchanged; false retains resources and data."
  default     = true
}
variable "allow_unreserved_processing_functions" {
  type        = bool
  default     = false
  nullable    = false
  description = "Narrow low-quota personal automatic-processing opt-in only. Never a general explicit-mode -1 allowance; pause with false and concurrency zero."
}
variable "runtime_controls" {
  description = "Optional independent runtime controls. Null preserves historical runtime_enabled behavior; explicit controls require runtime_enabled=false. Omitted functions remain paused."
  type = object({
    function_concurrency         = optional(map(number), {})
    media_data_enabled           = optional(bool, false)
    api_endpoint_enabled         = optional(bool, false)
    public_signup_enabled        = optional(bool, false)
    queue_consumers              = optional(set(string), [])
    schedules                    = optional(set(string), [])
    upload_notifications_enabled = optional(bool, false)
  })
  default = null
  validation {
    condition = !var.allow_unreserved_processing_functions ? true : try(
      var.region == "us-east-1" && var.prefix == "ecoguard3184" && var.environment == "personal" &&
      length(var.allowed_account_ids) == 1 && contains(var.allowed_account_ids, "011154879765") &&
      var.manage_execution_role && var.execution_role_arn == "" && var.manage_media_bucket && var.deploy_api &&
      !var.runtime_enabled && var.manage_upload_notifications == true && var.manage_ingest_ecr_pull_policy &&
      var.allow_root_bucket_inventory_while_paused &&
      can(regex("^011154879765[.]dkr[.]ecr[.]us-east-1[.]amazonaws[.]com/ecoguard3184-personal-worker@sha256:[0-9a-f]{64}$", var.worker_image)) &&
      var.inference_url == "https://ecoguard-inference-adlnb7yumq-uc.a.run.app" &&
      var.google_invoker_email == "ecoguard-aws-invoker@ecoguard-fit3184-a2-2026.iam.gserviceaccount.com" &&
      var.runtime_controls.function_concurrency == tomap({ ingest = -1, infer = -1, outbox = -1 }) &&
      var.runtime_controls.media_data_enabled && !var.runtime_controls.api_endpoint_enabled &&
      !var.runtime_controls.public_signup_enabled && var.runtime_controls.upload_notifications_enabled &&
      var.runtime_controls.queue_consumers == toset(["ingest", "infer"]) &&
      var.runtime_controls.schedules == toset(["outbox"]), false
    )
    error_message = "Unreserved opt-in is only for the exact personal three-function automatic profile, own image/role/bucket, two capped consumers and outbox schedule; all public/other entries must stay off."
  }
  validation {
    condition     = var.runtime_controls == null ? true : !var.runtime_enabled
    error_message = "Explicit runtime_controls require runtime_enabled=false."
  }
  validation {
    condition = var.runtime_controls == null ? true : alltrue([
      for name, concurrency in var.runtime_controls.function_concurrency :
      contains(["api", "ingest", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment"], name) &&
      try(floor(concurrency) == concurrency && (
        concurrency >= 0 || (var.allow_unreserved_processing_functions && concurrency == -1 && contains(["ingest", "infer", "outbox"], name))
      ), false)
    ])
    error_message = "Function names must be known and reserved concurrency nonnegative integers, except the separately validated exact personal three-function unreserved profile."
  }
  validation {
    condition = var.runtime_controls == null ? true : alltrue([
      for name, concurrency in var.runtime_controls.function_concurrency :
      try(concurrency == 0 || (var.deploy_api && (name != "ingest" || var.worker_image != "")), false)
    ])
    error_message = "Positive reservations require deployed functions, including a worker_image for ingest."
  }
  validation {
    condition = var.runtime_controls == null ? true : alltrue([
      for name in var.runtime_controls.queue_consumers :
      contains(["ingest", "infer", "delete", "notify"], name) && var.deploy_api &&
      try(lookup(var.runtime_controls.function_concurrency, name, 0) >= 2 ||
      (var.allow_unreserved_processing_functions && contains(["ingest", "infer"], name) && lookup(var.runtime_controls.function_concurrency, name, 0) == -1), false) &&
      (!contains(["ingest", "infer"], name) || (var.worker_image != "" && var.inference_url != "" && var.google_invoker_email != ""))
    ])
    error_message = "Enabled consumers require ready deployed functions and reservation at least two, except exact personal ingest/infer unreserved opt-in; mapping caps remain two."
  }
  validation {
    condition = var.runtime_controls == null ? true : alltrue([
      for name in var.runtime_controls.schedules :
      contains(["outbox", "cleanup"], name) && var.deploy_api &&
      try(lookup(var.runtime_controls.function_concurrency, name, 0) >= 1 ||
      (var.allow_unreserved_processing_functions && name == "outbox" && lookup(var.runtime_controls.function_concurrency, name, 0) == -1), false)
    ])
    error_message = "Enabled schedules require positive reserved concurrency, except the exact opted-in personal unreserved outbox target."
  }
  validation {
    condition = var.runtime_controls == null ? true : (
      !var.runtime_controls.api_endpoint_enabled ||
      (var.deploy_api && try(lookup(var.runtime_controls.function_concurrency, "api", 0) >= 1, false))
    )
    error_message = "An enabled API endpoint requires its deployed API function to have positive reserved concurrency."
  }
  validation {
    condition = var.runtime_controls == null ? true : (
      !var.runtime_controls.upload_notifications_enabled ||
      (var.deploy_api && var.worker_image != "" && var.inference_url != "" && var.google_invoker_email != "" && var.manage_upload_notifications != false)
    )
    error_message = "Enabled upload destinations require complete processing bindings and a managed notification resource."
  }
}
variable "manage_upload_notifications" {
  type        = bool
  description = "Null preserves the legacy processing_ready resource count. Explicit true retains the resource even when destinations are disabled; false leaves notifications unmanaged. Keep true after first adoption."
  default     = null
}
variable "lambda_zip" {
  type    = string
  default = "../../build/aws-lambda.zip"
}
variable "worker_image" {
  type        = string
  description = "Immutable ECR image digest containing FFmpeg. Empty keeps preprocessing disabled."
  default     = ""
}
variable "inference_url" {
  type    = string
  default = ""
}
variable "google_invoker_email" {
  type    = string
  default = ""
}
variable "web_url" {
  type    = string
  default = "http://127.0.0.1:5173"
}
variable "model_manifest_version" {
  type    = string
  default = "ecoguard-models-2026-10-08-v3"
}
variable "lex_bot_id" {
  type    = string
  default = ""
}
variable "lex_alias_id" {
  type    = string
  default = ""
}
variable "manage_ingest_ecr_pull_policy" {
  type        = bool
  default     = false
  nullable    = false
  description = "Opt in to the exact personal ingest-only Lambda service pull policy. Defaults false to preserve historical/course behavior; this grants no application invocation."
}
