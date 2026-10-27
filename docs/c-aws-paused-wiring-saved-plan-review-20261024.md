# Paused AWS ingest wiring - saved plan review

The actual normal-refresh plan passed on 24 October 2026 at 02:50:24 UTC for AWS account `011154879765`, region `us-east-1`, source `ec151b22a6fb47b21d003f268065b068376f586a`. It changes the synchronized physical55 checkpoint to59 managed resources: **4 creates,8 updates,47 no-ops**, no resource drift. No apply or permission change has run.

Saved binary SHA256: `32d2cb7f5f24f1673b72fc3dfa49461e0503c18972122740e15ed4afb02c9a5f`. The complete selected hashes and exact permission edges are in the [review evidence](../evidence/c-aws-paused-wiring-saved-plan-review-20261024.json). Original binary, full plan, input manifests and raw review remain in the AWS CloudShell state-owning checkout.

## Proposed resource changes

- Create the named ingest log group, Image-based ingest Lambda, disabled ingest SQS mapping, and restricted ECR repository policy.
- Add the fixed private Google Run URL and dedicated invoker identity to the seven existing ZIP function environments. Add only the ingest log-stream ARN to the existing project runtime log statement.
- Keep all eight functions at reserved concurrency0, all four SQS mappings disabled, both schedules disabled, API endpoint disabled, signup restricted and S3 data paused. Retain the already approved exact-root bucket-listing exception.

## Exact new permissions

The repository policy grants `lambda.amazonaws.com` only `ecr:BatchGetImage` and `ecr:GetDownloadUrlForLayer` on `ecoguard3184-personal-worker`. Both conditions must match: source account `011154879765` and the sole source function `arn:aws:lambda:us-east-1:011154879765:function:ecoguard3184-personal-ingest`.

The existing execution role gains only `logs:CreateLogStream` and `logs:PutLogEvents` on `arn:aws:logs:us-east-1:011154879765:log-group:/aws/lambda/ecoguard3184-personal-ingest:log-stream:*`. This enables image retrieval and project log output. No new human recipient or credential is created.

## Execution and funding boundary

Apply this exact saved binary at most once, after action-time confirmation and a fresh eligible-credit/account check. Additional personal spending remains A$0; storage may consume the verified existing credits, which are not a hard spending cap. The helper must stop on unexpected state, permissions, image pull or post-verification differences. It cannot automatically replan, retry, broaden ECR permissions, enable processing, upload media or invoke the application.

Successful application will establish paused runtime deployment. Actual AWS-role federation, automatic media processing and pause/restore acceptance still require separate bounded tests. Original blocked plans1,2 and3 remain retained failures; this plan does not rewrite them.
