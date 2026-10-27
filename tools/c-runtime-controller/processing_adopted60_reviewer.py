"""Pure review of one NEW normal-refresh paused95 to active60 saved plan.

No clients, subprocess, writes or gate main. The parent preparer binds actual
raw95/5de335 and full native physical export; this pure gate requires zero drift
and exact full physical/prior values. Only eight existing runtime controls may
update; output configuration is separate from live API pause. No apply authority.
"""
import copy
import json
from datetime import datetime, timezone


def require(ok, message):
    if not ok:
        raise ValueError(message)


def scoped_pause_policy(g, value):
    require(type(value) is str, 'Native S3 policy must remain a JSON string')
    require(g.BASE.root_inventory_policy_is_scoped(json.loads(value)),
            'Only exact approved paused TLS/object-deny/root-list policy allowed')


def control_addresses(g):
    return g.UPDATES | {g.NOTIFICATION}


def paused_profile(g, values, *, image, zip_filename):
    """Direct original profile predicates, with actual paused95 cap2 retained."""
    require(set(values) == g.WIRED | {g.NOTIFICATION}, 'Exact adopted paused60 inventory required')
    for name, address in g.FUNCTIONS.items():
        v = values[address]
        require(type(v.get('reserved_concurrent_executions')) is int and v['reserved_concurrent_executions'] == 0,
                'All eight paused reservations must be exactly zero')
        require(v.get('role') == g.BASE.EXECUTION_ROLE and v.get('function_name') == g.PREFIX+'-'+name
                and v.get('architectures') == ['x86_64'], 'Function identity differs')
        env = v.get('environment', [])
        require(len(env) == 1 and all(env[0].get('variables', {}).get(k) == expected
                for k,expected in g.WIRING.ENV_BINDINGS.items())
                and env[0]['variables'].get('ECO_GOOGLE_CREDENTIALS_FILE') == '/var/task/config/google-wif.json',
                'Function Run/WIF binding differs')
        if name == 'ingest':
            require(v.get('package_type') == 'Image' and v.get('image_uri') == image
                    and all(v.get(k) in (None, '') for k in ('filename','runtime','handler')),
                    'Ingest immutable Image binding differs')
        else:
            require(v.get('package_type') == 'Zip' and v.get('runtime') == 'python3.12'
                    and v.get('filename') == zip_filename
                    and v.get('source_code_hash') == g.base64.b64encode(bytes.fromhex(g.WIRING.ZIP_SHA)).decode(),
                    'Reviewed unchanged ZIP differs')
    for name,address in g.MAPPINGS.items():
        v = values[address]
        cap = [{'maximum_concurrency':2}] if name in ('ingest','infer') else []
        require(v.get('enabled') is False and g.same(v.get('state'),'Disabled') and g.same(v.get('scaling_config'),cap)
                and v.get('event_source_arn') == f'arn:aws:sqs:{g.BASE.REGION}:{g.BASE.ACCOUNT}:{g.PREFIX}-{name}'
                and v.get('function_name') == f'arn:aws:lambda:{g.BASE.REGION}:{g.BASE.ACCOUNT}:function:{g.PREFIX}-{name}'
                and type(v.get('batch_size')) is int and v['batch_size'] == 1
                and v.get('function_response_types') == ['ReportBatchItemFailures'],
                'Disabled mapping identity/batch/retained cap differs')
    require(all(values[a].get('state') == 'DISABLED' for a in g.RULES.values()), 'All paused schedules must be disabled')
    require(values[g.MODULE+'aws_apigatewayv2_api.app[0]'].get('disable_execute_api_endpoint') is True,
            'API endpoint must remain off')
    signup = values[g.MODULE+'aws_cognito_user_pool.users'].get('admin_create_user_config', [])
    require(len(signup) == 1 and signup[0].get('allow_admin_create_user_only') is True, 'Public signup must remain off')
    require(values[g.BUCKET_POLICY].get('bucket') == g.BUCKET, 'Policy bucket differs')
    scoped_pause_policy(g, values[g.BUCKET_POLICY].get('policy'))
    checks = []
    g.BASE.inspect_bucket_security(lambda suffix:values.get(g.MODULE+suffix, {}),
                                  lambda name,ok:checks.append((name,bool(ok))), root_inventory_while_paused=True)
    require(all(ok for _,ok in checks), 'Paused bucket privacy/security differs')
    require(g.repaired_ecr_policy_is_scoped(values[g.FOCUS.POLICY]['policy'])
            and values[g.FOCUS.POLICY].get('repository') == g.FOCUS.REPOSITORY,
            'ECR retrieval policy differs')
    value = values[g.NOTIFICATION]
    require(value.get('id') == g.BUCKET
            and g.same({k:v for k,v in value.items() if k != 'id'},g.notification(False)),
            'Adopted paused notification must be completely empty and owned')


def refreshed_pause(g, document, physical):
    """Fresh normal prior must exactly equal the actual reconciled snapshot."""
    old = g.managed(physical['values']['root_module'])
    prior = g.managed(document['prior_state']['values']['root_module'])
    require(set(old) == set(prior) == g.WIRED | {g.NOTIFICATION} and len(old) == 60,
            'Complete physical60/refreshed60 inventories required')
    rows = document.get('resource_drift', [])
    require(type(rows) is list and rows == [], 'New drift is not reviewed; preserve the native plan for independent review')
    require(g.same(old,prior), 'Full refreshed prior differs from reconciled paused60 checkpoint')
    return old,prior


def inspect_plan(g, document, physical, *, image, zip_filename, window_seconds,
                 quota_evidence=None, quota_evidence_sha256=None, review_time=None):
    """g is the unchanged hash-verified source47 processing gate, never its main."""
    require(type(window_seconds) is int and 1 <= window_seconds <= 600, 'Bounded window must remain1..600')
    require(type(image) is str and g.FOCUS.IMAGE_PATTERN.fullmatch(image), 'Exact personal immutable Image URI required')
    require(type(zip_filename) is str and zip_filename.startswith('/') and zip_filename.endswith('.zip'), 'Absolute reviewed ZIP required')
    require(document.get('complete') is True and document.get('errored') is False
            and not document.get('deferred_changes') and not document.get('action_invocations'),
            'Incomplete/errored/deferred/action plan')
    quota = g.reviewed_low_quota(quota_evidence, quota_evidence_sha256, review_time)
    old, prior = refreshed_pause(g, document, physical)
    future_root = document['planned_values']['root_module']
    future = g.managed(future_root)
    # Validate original paused values directly; no synthetic rewrite passed to
    # the old profile (which predates disabled mappings retaining cap2).
    paused_profile(g,old,image=image,zip_filename=zip_filename)
    g.profile(future, active=True, adopted=True, image=image, zip_filename=zip_filename)
    require(set(future) == set(prior) and future[g.NOTIFICATION].get('id') == g.BUCKET,
            'Adopted resource must remain present with known exact bucket identity')
    identity = {'account_id':g.BASE.ACCOUNT, 'id':g.BASE.ACCOUNT,
                'user_id':g.BASE.ACCOUNT, 'arn':'arn:aws:iam::'+g.BASE.ACCOUNT+':root'}
    for root in (physical['values']['root_module'], document['prior_state']['values']['root_module']):
        data = [r for r in g.BASE.resources(root) if r.get('mode') != 'managed']
        require(len(data) == 1 and data[0].get('mode') == 'data'
                and data[0].get('address') == g.MODULE+'data.aws_caller_identity.current'
                and data[0].get('type') == 'aws_caller_identity' and g.same(data[0].get('values'), identity),
                'Exact known root caller data profile required')
    require(not [r for r in g.BASE.resources(future_root) if r.get('mode') != 'managed']
            and not [r for r in document.get('resource_changes', []) if r.get('mode') != 'managed'],
            'No planned data-resource read/change allowed')
    variables = document.get('variables', {})
    for name, expected in {'deployment_stage':'processing-bounded','adopt_upload_notifications':'true',
                           'worker_image':image,'lambda_zip':zip_filename,'inference_url':g.WIRING.RUN_URL}.items():
        require(g.same(variables.get(name, {}).get('value'), expected), 'Explicit native input differs: '+name)
    call = document.get('configuration', {}).get('root_module', {}).get('module_calls', {}).get('ecoguard', {})
    require(call.get('source') == '../..' and not any(k in call for k in ('count_expression','for_each_expression','depends_on','providers')),
            'Module source/scope differs')
    expressions = call.get('expressions', {})
    for name, expected in g.BASE.ROOT_INPUTS.items():
        if name not in {'worker_image','inference_url','google_invoker_email'}:
            require(g.same(expressions.get(name), {'constant_value':expected}), 'Static module input differs: '+name)
    require(g.same(expressions.get('allow_root_bucket_inventory_while_paused'), {'constant_value':True})
            and g.same(expressions.get('manage_upload_notifications'), {'references':['var.adopt_upload_notifications']})
            and g.same(expressions.get('allow_unreserved_processing_functions'), {'references':['var.deployment_stage']}),
            'Explicit scoped root inventory/notification ownership/unreserved opt-in differs')
    rows = document.get('resource_changes')
    require(type(rows) is list and len(rows) == 60 and len({r.get('address') for r in rows}) == 60
            and {r.get('address') for r in rows} == set(prior), 'Exactly sixty complete native change rows required')
    updates = control_addresses(g)
    paths = {}
    for row in rows:
        address, change = row['address'], row['change']
        require(change.get('actions') == (['update'] if address in updates else ['no-op'])
                and row.get('provider_name') == 'registry.terraform.io/hashicorp/aws'
                and not any(row.get(k) or change.get(k) for k in ('previous_address','deposed','importing','replace_paths'))
                and g.same(change.get('before'), prior[address]), 'Unexpected action or complete before-value mismatch')
        expected = copy.deepcopy(prior[address])
        if address in {g.FUNCTIONS[n] for n in ('ingest','infer','outbox')}:
            expected['reserved_concurrent_executions'] = -1
        elif address in {g.MAPPINGS[n] for n in ('ingest','infer')}:
            expected['enabled'] = True
        elif address == g.RULES['outbox']:
            expected['state'] = 'ENABLED'
        elif address == g.BUCKET_POLICY:
            require(type(future[address].get('policy')) is str
                    and g.same(json.loads(future[address]['policy']),g.tls_policy()),
                    'Activation policy must be the complete exact TLS-only policy')
            expected['policy'] = future[address]['policy']
        elif address == g.NOTIFICATION:
            expected['queue'] = g.notification(True)['queue']
        # Existing field-specific metadata unknown catalogue only. Notification
        # is an existing resource: its id/security/destination cannot be unknown.
        paths[address] = g.compared(prior[address], change['after'], future[address],
                                    change.get('after_unknown', {}), address, expected)
    before_outputs = physical['values'].get('outputs', {})
    prior_outputs = document['prior_state']['values'].get('outputs', {})
    outputs = document['planned_values'].get('outputs', {})
    require(set(before_outputs) == g.OUTPUTS and g.same(before_outputs, prior_outputs)
            and g.same(before_outputs, outputs), 'All eleven native output descriptors must be unchanged')
    require(before_outputs['runtime_enabled']['value'] is False
            and before_outputs['processing_enabled']['value'] is True
            and before_outputs['deployment_stage']['value'] == 'processing-bounded'
            and g.same(before_outputs['runtime_controls']['value'], g.controls(True, True)),
            'Saved stage output configuration differs; outputs are not live API control observations')
    changes = document.get('output_changes', {})
    require(set(changes) == g.OUTPUTS, 'Exactly eleven output change rows required')
    for name, row in changes.items():
        require(row.get('actions') == ['no-op'] and g.same(row.get('before'), before_outputs[name]['value'])
                and g.same(row.get('after'), before_outputs[name]['value'])
                and not g.WIRING.unknown_paths(row.get('after_unknown', False))
                and row.get('before_sensitive') is False and row.get('after_sensitive') is False,
                'Root output action/value/sensitivity differs: '+name)
    return {'status':'offline-paused95-processing-plan-passed','mode':'reactivate-paused-adopted',
            'priorManagedResources':60,'managedResources':60,'creates':0,'updates':8,'noops':52,'deletes':0,
            'fullPhysicalPriorEqual':True,'physicalPriorFullyEqual':True,'fullReviewedRefreshedPriorEqual':True,
            'resourceDriftResources':0,'allOther52PhysicalValuesExact':True,
            'allElevenNativeOutputDescriptorsUnchanged':True,'savedRawStateNotificationAlreadyEmpty':True,
            'disabledMappingsRetainExistingCapTwo':True,'noNewIAMOrService':True,'securityUnknownsAllowed':False,
            'reviewedUnknownPaths':{a:p for a,p in paths.items() if p},'maximumReviewedWindowSeconds':window_seconds,
            'lowQuotaEvidence':quota,'quotaAtHistoricalPlanTimeOnly':True,'freshQuotaRequiredBeforeActivation':True,
            'unreservedProcessingOptIn':True,'outboxReservationCapOne':False,'applyAuthorized':False,
            'timerCreated':False,'runtimeActivated':False,'automaticFlowVerified':False,
            'normalRefreshModeMustBeProvenByStartedArgvAndBinaryHash':True}
