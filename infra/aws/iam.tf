# Optional personal-account runtime identity. The historical LabRole is never
# imported, edited, attached to, or replaced by these resources.
locals {
  runtime_account = data.aws_caller_identity.current.account_id
  # Deterministic ARNs keep the whole policy visible in a first-create plan.
  # They name only resources managed by this module and this account/region.
  runtime_table_arns = [for table in sort(keys(local.tables)) :
    "arn:aws:dynamodb:${var.region}:${local.runtime_account}:table/${local.name}-${table}"
  ]
  runtime_queue_arns = [for queue in sort(keys(local.queue_timeout)) :
    "arn:aws:sqs:${var.region}:${local.runtime_account}:${local.name}-${queue}"
  ]
  runtime_log_stream_arns = [for function in sort(keys(merge(local.zip_functions, local.has_worker ? { ingest = 120 } : {}))) :
    "arn:aws:logs:${var.region}:${local.runtime_account}:log-group:/aws/lambda/${local.name}-${function}:log-stream:*"
  ]
  runtime_topic_arn = "arn:aws:sns:${var.region}:${local.runtime_account}:${local.name}-user-*"
  runtime_policy = {
    Version = "2012-10-17"
    Statement = concat([
      {
        Sid    = "ProjectTableRecords"
        Effect = "Allow"
        # TransactWriteItems authorizes each enclosed Put/Delete action. The
        # SDK method name is not an IAM action; no Update/Batch/Admin is used.
        Action   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = local.runtime_table_arns
      },
      {
        Sid      = "ProjectBucketListing"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:ListBucketVersions"]
        Resource = [local.bucket_arn]
      },
      {
        Sid    = "ProjectMediaObjects"
        Effect = "Allow"
        # Head/Copy use GetObject + PutObject; version cleanup needs both deletes.
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject", "s3:DeleteObjectVersion"]
        Resource = ["${local.bucket_arn}/*"]
      },
      {
        Sid    = "ProjectWorkQueues"
        Effect = "Allow"
        # SendMessage is used by AwsQueue; receive/delete/attributes are the
        # Lambda SQS event-source poller's permissions. No DLQ/admin access.
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = local.runtime_queue_arns
      },
      {
        Sid      = "ProjectNotificationTopics"
        Effect   = "Allow"
        Action   = ["sns:CreateTopic", "sns:ListSubscriptionsByTopic", "sns:Publish"]
        Resource = [local.runtime_topic_arn]
      },
      {
        Sid       = "ProjectEmailSubscriptions"
        Effect    = "Allow"
        Action    = ["sns:Subscribe"]
        Resource  = [local.runtime_topic_arn]
        Condition = { StringEquals = { "sns:Protocol" = "email" } }
      },
      {
        Sid    = "RegionalAnimalLabelDetection"
        Effect = "Allow"
        # DetectLabels takes image bytes and has no resource-level ARN. This is
        # the sole Resource="*" and only for this action in the selected region.
        Action    = ["rekognition:DetectLabels"]
        Resource  = ["*"]
        Condition = { StringEquals = { "aws:RequestedRegion" = var.region } }
      }
      ], length(local.runtime_log_stream_arns) > 0 ? [{
        Sid    = "ProjectFunctionLogs"
        Effect = "Allow"
        # Terraform creates the groups before Lambda; runtime cannot create any.
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = local.runtime_log_stream_arns
        }] : [], var.lex_bot_id != "" && var.lex_alias_id != "" ? [{
        Sid      = "ConfiguredLexAlias"
        Effect   = "Allow"
        Action   = ["lex:RecognizeText"]
        Resource = ["arn:aws:lex:${var.region}:${local.runtime_account}:bot-alias/${var.lex_bot_id}/${var.lex_alias_id}"]
    }] : [])
  }
}

resource "aws_iam_role" "runtime" {
  count       = var.manage_execution_role ? 1 : 0
  name        = "${local.name}-lambda"
  path        = "/"
  description = "Aussie EcoGuard project Lambda runtime"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "runtime" {
  count = var.manage_execution_role ? 1 : 0
  name  = "${local.name}-runtime"
  # Name is known in the first plan and still depends on this managed role.
  role   = aws_iam_role.runtime[0].name
  policy = jsonencode(local.runtime_policy)
}
