terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.0, < 8.0" }
  }
  backend "local" {
    path = "state/terraform.tfstate"
  }
}

# The existing provider-containing module must stay unconditional. Child-module
# deployment.auto.tfvars are not loaded by this separate root.
module "ecoguard" {
  source = "../.."

  project_id            = "ecoguard-fit3184-a2-2026"
  identity_only         = var.deployment_stage != "private-inference"
  prepare_registry      = var.deployment_stage != "identity"
  model_storage_enabled = false
  # The personal runtime is bounded by expiring credits and must be removable
  # with a separately reviewed cleanup plan. Shared/historical defaults stay true.
  inference_deletion_protection   = false
  inference_service_max_instances = 1
  region                          = "us-central1"
  prefix                          = "ecoguard3184"
  aws_account_id                  = "011154879765"
  aws_role_name                   = "ecoguard3184-personal-lambda"
  aws_region                      = "us-east-1"
  manifest_sha256                 = "639595e1e9ffe18cb11ead1c7480ffe7a31bf767f6cbaf6b8375829227a569ae"
  image                           = var.deployment_stage == "private-inference" ? var.inference_image : ""
  cognito_issuer                  = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Sog8ekMM1"
  cognito_client_id               = "5gu7g1rgkmabdd551h5k3350f6"
  media_bucket                    = "ecoguard3184-personal-011154879765-media"
  inference_environment           = {}
}

output "deployment_identity" {
  value = {
    project_id     = module.ecoguard.project_id
    project_number = tostring(module.ecoguard.project_number)
  }
  precondition {
    condition     = tostring(module.ecoguard.project_number) == "995070689587"
    error_message = "The personal root requires project number 995070689587. Stop if the project identity differs."
  }
}
output "invoker_service_account" { value = module.ecoguard.invoker_service_account }
output "wif_provider_audience" { value = module.ecoguard.wif_provider_audience }
output "repository" { value = module.ecoguard.repository }
output "inference_url" { value = module.ecoguard.inference_url }
