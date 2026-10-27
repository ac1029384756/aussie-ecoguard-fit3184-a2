locals {
  # Keep every legacy branch explicit. In particular, legacy scaling_config
  # existence follows runtime_enabled, even when inference bindings are absent.
  controlled_runtime = var.runtime_controls != null
  function_concurrency = local.controlled_runtime ? merge(
    { for name in ["api", "ingest", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment"] : name => 0 },
    var.runtime_controls.function_concurrency
  ) : { for name in ["api", "ingest", "infer", "delete", "notify", "outbox", "cleanup", "lex_fulfillment"] : name => (var.runtime_enabled ? -1 : 0) }

  media_data_enabled    = local.controlled_runtime ? var.runtime_controls.media_data_enabled : var.runtime_enabled
  api_endpoint_enabled  = local.controlled_runtime ? var.runtime_controls.api_endpoint_enabled : var.runtime_enabled
  public_signup_enabled = local.controlled_runtime ? var.runtime_controls.public_signup_enabled : var.runtime_enabled
  queue_consumers_enabled = {
    for name in ["ingest", "infer", "delete", "notify"] : name => (
      local.controlled_runtime ? contains(var.runtime_controls.queue_consumers, name) :
      (var.runtime_enabled && (!contains(["ingest", "infer"], name) || local.processing_ready))
    )
  }
  queue_scaling_enabled = {
    for name in ["ingest", "infer", "delete", "notify"] : name => (
      local.controlled_runtime ? local.queue_consumers_enabled[name] : var.runtime_enabled
    )
  }
  schedules_enabled = {
    for name in ["outbox", "cleanup"] : name => (
      local.controlled_runtime ? contains(var.runtime_controls.schedules, name) : var.runtime_enabled
    )
  }
  manage_upload_notifications  = var.manage_upload_notifications == null ? local.processing_ready : var.manage_upload_notifications
  upload_notifications_enabled = local.controlled_runtime ? var.runtime_controls.upload_notifications_enabled : var.runtime_enabled
}
