variable "project_id" { type = string }
variable "identity_only" {
  type        = bool
  description = "IAM/WIF only by default; prepare_registry may explicitly add its registry/API. No inference compute or model storage while true."
  default     = true
}
variable "prepare_registry" {
  type        = bool
  description = "Opt in to the image registry/API while retaining identity_only=true; no runtime service or invoker grant."
  default     = false
}
variable "model_storage_enabled" {
  type        = bool
  description = "Retain the historical runtime model bucket/API/reader by default; disable only when locked artifacts use direct HTTPS."
  default     = true
}
variable "inference_deletion_protection" {
  type        = bool
  description = "Protect historical inference services by default; a bounded personal deployment may explicitly allow reviewed cleanup."
  default     = true
}
variable "inference_service_max_instances" {
  type        = number
  description = "Optional service-wide automatic scaling cap; null preserves historical revision-only scaling."
  default     = null
  validation {
    condition = var.inference_service_max_instances == null ? true : (
      var.inference_service_max_instances >= 1 && floor(var.inference_service_max_instances) == var.inference_service_max_instances
    )
    error_message = "An explicit service instance cap must be a positive integer."
  }
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "prefix" {
  type    = string
  default = "ecoguard3184"
}
variable "aws_account_id" { type = string }
variable "aws_role_name" {
  type    = string
  default = "LabRole"
}
variable "image" {
  type    = string
  default = ""
}
variable "cognito_issuer" {
  type    = string
  default = ""
}
variable "cognito_client_id" {
  type    = string
  default = ""
}
variable "media_bucket" {
  type    = string
  default = ""
}
variable "manifest_sha256" {
  type    = string
  default = "639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae"
  validation {
    condition     = var.manifest_sha256 == filesha256("${path.module}/../../config/model.locked.json")
    error_message = "Manifest hash must match this checkout's config/model.locked.json. Rebuild the image when the locked manifest changes."
  }
}
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "inference_environment" {
  type    = map(string)
  default = {}
}
