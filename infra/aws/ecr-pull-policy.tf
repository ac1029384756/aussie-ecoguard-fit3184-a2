# Opt-in only: historical/course deployments retain their existing policy path.
# The exact ARN uses the configured name, never the function resource, to avoid
# a cycle: repository policy -> Lambda -> repository policy.
resource "aws_ecr_repository_policy" "lambda_ingest" {
  count      = var.manage_ingest_ecr_pull_policy && local.has_worker ? 1 : 0
  repository = aws_ecr_repository.worker.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "LambdaECRImageRetrievalPolicy"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
      Condition = {
        ArnEquals    = { "aws:SourceArn" = "arn:aws:lambda:${var.region}:${local.runtime_account}:function:${local.name}-ingest" }
        StringEquals = { "aws:SourceAccount" = local.runtime_account }
      }
    }]
  })
  lifecycle {
    precondition {
      condition = (
        local.runtime_account == "011154879765" && var.region == "us-east-1" && local.name == "ecoguard3184-personal" &&
        can(regex("^011154879765[.]dkr[.]ecr[.]us-east-1[.]amazonaws[.]com/ecoguard3184-personal-worker@sha256:[0-9a-f]{64}$", var.worker_image))
      )
      error_message = "The reviewed ECR pull policy is only for the exact personal us-east-1 ingest function and immutable worker image."
    }
  }
}
