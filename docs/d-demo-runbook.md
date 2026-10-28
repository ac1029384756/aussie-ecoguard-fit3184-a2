# D demo and evidence runbook

## Pre-flight

- Record commit SHA, AWS account/region, Lex bot version/alias, Lambda version, model manifest, and
  test run ID. Confirm the environment is authorized and within the A$0 extra-spend boundary.
- Confirm the test SNS subscription reports `ACTIVE`; `PendingConfirmation` is not a pass.
- Seed only licensed, non-sensitive assets from `evidence/d-acceptance-dataset-manifest.csv`.
- Open the web application, one redacted CloudWatch view, and the controlled test inbox.

## LEX 01 - positive conversation

1. Sign in and open the embedded chatbot.
2. Send `show me`; verify Lex elicits `species`.
3. Reply `foxes`, then run `show me two foxes` and a date-filtered query.
4. Verify returned cards are clickable and every opened item is authorized for the current user.
5. Run `find my ginger cat`; verify only public sightings are returned and the UI states that results
   are possible matches, not confirmed identities.

## LEX 02 - authorization and failure cases

- Submit an invalid count/date and verify a controlled message rather than a crash.
- Reuse another user's session ID and verify rejection.
- Sign out/switch accounts and verify the previous chat/results are not retained.
- Invoke the app while Lex IDs are absent and verify an explicit unavailable error, not simulated data.

## MAIL 01 - positive and negative cases

1. Create a `fox` alert and confirm it through the controlled inbox.
2. Without refreshing the subscriptions page, process a readable fox sighting. Verify one email lists
   `fox` and contains the stable authenticated media-page link.
3. Replay the same outbox event and verify no second application publish.
4. Verify no publish for pending confirmation, cancelled subscription, unrelated tag, unreadable
   private media, stale media version, deleted/not-ready media, and removed monitored tag.
5. Record SNS message ID for the positive case and delivery-ledger state for all cases. Redact email,
   tokens, signed URLs, and media containing personal information.

## Recovery during the live demo

- A controlled Lex/SNS error is demonstrated and explained; it is not relabelled as a pass.
- If email delivery is delayed, show the SNS publish ID and earlier timestamped inbox evidence, then
  continue. Do not claim a pending channel was delivered.
- Keep preprocessed evidence for timing, but still trigger at least one real live operation.

## Evidence layout

Store each run under `evidence/runs/<runId>/rubric/` using the IDs already defined in the team plan.
Each record includes expected/actual result, status, commit, environment, asset ID, request/job ID,
timestamp, and redacted evidence path.
