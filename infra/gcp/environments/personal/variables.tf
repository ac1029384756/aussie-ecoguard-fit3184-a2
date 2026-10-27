variable "deployment_stage" {
  type        = string
  description = "Explicit reviewed stage: retain deployed identity, prepare its registry, or add private inference. Source defaults do not activate runtime."
  default     = "identity"
  validation {
    condition     = contains(["identity", "registry", "private-inference"], var.deployment_stage)
    error_message = "deployment_stage must be identity, registry, or private-inference. Each increment requires its own reviewed saved plan."
  }
}

variable "inference_image" {
  type        = string
  description = "Empty before private inference; then the reviewed immutable digest in this project's exact inference repository path."
  default     = ""
  validation {
    condition = var.deployment_stage == "private-inference" ? can(regex(
      "^us-central1-docker\\.pkg\\.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:[0-9a-f]{64}$", var.inference_image
    )) : var.inference_image == ""
    error_message = "Private inference requires the reviewed us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/inference@sha256:<64 lowercase hex> digest; all earlier stages require an empty image."
  }
}
