# Mock plans only; no credentials, real ZIP, resource write or application call.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "011154879765", arn = "arn:aws:iam::011154879765:root", user_id = "offline-mock" }
  }
}
variables {
  region              = "us-east-1"
  prefix              = "ecoguard3184"
  environment         = "personal"
  manage_media_bucket = true
  runtime_enabled     = false
  deploy_api          = false
}
run "legacy_default_preserves_every_deny" {
  command = plan
  assert {
    condition = jsondecode(aws_s3_bucket_policy.media_tls.policy) == {
      "Version" = "2012-10-17"
      "Statement" = [{
        "Sid"       = "DenyInsecureTransport"
        "Effect"    = "Deny"
        "Principal" = "*"
        "Action"    = "s3:*"
        "Resource"  = ["arn:aws:s3:::ecoguard3184-personal-011154879765-media", "arn:aws:s3:::ecoguard3184-personal-011154879765-media/*"]
        "Condition" = {
          "Bool" = {
            "aws:SecureTransport" = "false"
          }
        }
        }, {
        "Sid"       = "DenyDataAccessWhileRuntimePaused"
        "Effect"    = "Deny"
        "Principal" = "*"
        "Action"    = ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:ListBucket", "s3:ListBucketVersions", "s3:ListBucketMultipartUploads"]
        "Resource"  = ["arn:aws:s3:::ecoguard3184-personal-011154879765-media", "arn:aws:s3:::ecoguard3184-personal-011154879765-media/*"]
      }]
    }
    error_message = "Default false must preserve the exact original TLS and nine-action unconditional pause policy."
  }
}
run "exact_root_inventory_keeps_all_other_denies" {
  command = plan
  variables { allow_root_bucket_inventory_while_paused = true }
  assert {
    condition = jsondecode(aws_s3_bucket_policy.media_tls.policy) == {
      "Version" = "2012-10-17"
      "Statement" = [{
        "Sid"       = "DenyInsecureTransport"
        "Effect"    = "Deny"
        "Principal" = "*"
        "Action"    = "s3:*"
        "Resource"  = ["arn:aws:s3:::ecoguard3184-personal-011154879765-media", "arn:aws:s3:::ecoguard3184-personal-011154879765-media/*"]
        "Condition" = {
          "Bool" = {
            "aws:SecureTransport" = "false"
          }
        }
        }, {
        "Sid"       = "DenyDataAccessWhileRuntimePaused"
        "Effect"    = "Deny"
        "Principal" = "*"
        "Action"    = ["s3:GetObject*", "s3:PutObject*", "s3:DeleteObject*", "s3:RestoreObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts", "s3:ListBucketVersions", "s3:ListBucketMultipartUploads"]
        "Resource"  = ["arn:aws:s3:::ecoguard3184-personal-011154879765-media", "arn:aws:s3:::ecoguard3184-personal-011154879765-media/*"]
        }, {
        "Sid"       = "DenyBucketListingWhileRuntimePaused"
        "Effect"    = "Deny"
        "Principal" = "*"
        "Action"    = ["s3:ListBucket"]
        "Resource"  = ["arn:aws:s3:::ecoguard3184-personal-011154879765-media"]
        "Condition" = {
          "ArnNotEquals" = {
            "aws:PrincipalArn" = "arn:aws:iam::011154879765:root"
          }
        }
      }]
    }
    error_message = "Opt-in must exempt only exact account-root ListBucket, with TLS and all eight other deny actions unchanged."
  }
}
run "opt_in_does_not_add_a_deny_when_media_is_explicitly_enabled" {
  command = plan
  variables {
    allow_root_bucket_inventory_while_paused = true
    runtime_controls                         = { media_data_enabled = true }
  }
  assert {
    condition     = length(jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement) == 1 && jsondecode(aws_s3_bucket_policy.media_tls.policy).Statement[0].Sid == "DenyInsecureTransport"
    error_message = "The opt-in only changes paused inventory and must preserve the existing media-enabled branch."
  }
}
