# Member C: bounded runtime attempts and recovery — 25 October 2026

Three approved single-image attempts have not submitted a media fixture. Attempt 1 applied once and missed its original recovery target; attempt 2 stopped during startup before activation. Attempt 3 applied its separately reviewed saved plan once, passed active-profile verification, then stopped at the source-object absence check. It verified all eight controls paused within the original 600-second target, but its later continuous observation tail failed. Successful real images and automatic Lambda-role WIF/media results remain **0**.

## Attempt 1: applied once, failed before media input

| Result | Evidence and limitation |
|---|---|
| Saved plan applied once | Exit code 0; resulting AWS state serial 85, 60 managed resources. No replay is authorized. |
| Post-activation validation failed | Function `RevisionId` changed after concurrency updates, and S3 returned the known notification filter name as `Prefix`. The exact comparisons rejected the returned profiles. |
| Media/WIF processing | No image uploaded, no fixture seed submitted, no actual Lambda-to-GCP media or federated invocation verified. Successful real images: **0**. |
| First watchdog recovery | Four controls paused; four remaining reducers were blocked by profile comparison. Original records retained. |
| Operator recovery | The first operator helper failed during read-only checks without mutations. A revised helper then executed only the four previously unused reducers and verified their paused readbacks. |
| Independent post-check | At **03:09:48.489 UTC**, eight controls were paused in both observation rounds, project boundaries were checked, five complete table scans were empty, and eight queues had zero approximate counts. |
| Limits | No continuous application-drain proof; Terraform configuration convergence remains unverified. The eventual pause does not establish the original 600-second recovery target. |
| Later read-only collection | At **03:24:23.566 UTC**, all eight control groups passed, but the SDK boundary worker failed before completion. The attempt was retained without automatic retry, mutations, or media submission. |

## Attempt 2: startup stopped, no activation or image

This attempt had a new, single-use action-time approval. The actual final binder checked all 60 pins, an independent terminal identity check passed, and the fresh SDK backlog check passed before launch. Those preconditions did not establish application success.

| Result | Evidence and limitation |
|---|---|
| Startup failure | The watchdog recorded STOP reason `heartbeat`; the writer log recorded only `ValueError`. The exact failed assertion and writer exit timestamp were not recorded. |
| Activation and input | All 17 durable intents were audited: two child-spawn intents and 15 SDK boundary reads. There was no activation or external activation-call intent and no fixture seed/source-Put intent. Captured AWS outcomes recorded no mutations. The native read-only closeout still observed serial 85 and the same raw-state hash. This attempt did **not** apply the saved plan or submit an image. |
| Emergency controls | All eight controls read back paused at **T0+68.765734 seconds**. The pause receipt recorded `deadlineMissed=false`, closed input and a quiescent writer. This is distinct from proving application drain. |
| Continuous observation | The independent watchdog remained for **14 observation rounds / 570.038965 seconds**, covering the required 540-second tail after pause readback. Captured observations had paused controls, valid quota/funding gates, empty complete scans of all five tables, stable table hashes and no supervision timing gaps. These are sampled observations under the recorded plan, not a fresh balance check or proof of zero cost. |
| Drain acceptance | The final status remains **`drain-not-proven`**. Fixture-specific producer expiry, known-job terminal and unresolved-in-flight conditions were false because this fixture was never seeded. Empty tables do not prove the required fixture terminal/lease contract. No active lease, GCP idle state or cancellation of AWS/GCP in-flight requests was proved. |
| Process closeout | At **06:07:15.314 UTC**, both registered process incarnations were zombie (`Z`) and no live process matched the exact attempt nonce. Boot/user/start-ticks/process-group/session identities matched; no signal or retry was used. |

Independent local forensic review rehashed all 1,835 entries in the retained original manifest. It found that the original writer published one initial heartbeat, while the first watchdog ACK arrived at T0+5.916 seconds, later than the writer's five-second ACK wait. The continuous heartbeat thread started only after ACK and object setup. This makes a startup race strongly consistent with the timing; the generic writer error does not prove the precise failing assertion. Original failure records remain unchanged.

## Attempt 3: activated, source absence check blocked, paused on time

| Result | Evidence and limitation |
|---|---|
| New single-use scope | A new nonce, review packet and action-time approval were used. Saved plan `94c62df2…94ebc` was applied exactly once, exit0, without replan or automatic retry. It is now consumed. |
| Activation | The actual driver recorded `activeVerified=true`. The V14 lifecycle retained writer heartbeats while watchdog initialization took over six seconds, crossing the old five-second wait without the old heartbeat STOP. |
| Fixture boundary | The complete final archive has54 fixture outcomes:45 table scans (including later drain scans), eight queue-attribute reads and one source `HeadObject`. The earlier959-file interim capture contained19/10/8/1 respectively; it is not the final total. The HeadObject returned254 and was not accepted as a verified404. All34 final durable intents contain no fixture seed/source-Put or external fixture-write intent. No seed transaction or image PUT was sent. |
| Initial pause | STOP reason `verification`; input closed and writer quiesced. All eight final control readbacks passed at **T0+262.018945 seconds**, before the original T0+600 deadline (`deadlineMissed=false`). |
| Observation tail | Ten rounds covered **547.988794 seconds**, but rounds5 and10 contained eleven unverified S3 bucket CLI reads/timeouts. `continuousSafeObservations=false`, `watchdogIndependentlyRemainedThroughTail=false`, and `drain-not-proven` are preserved. `supervisionTimingGaps=[]` does not convert failed readbacks into continuous safety. The unseeded fixture separately cannot meet its terminal/lease conditions. |
| Final fallback | The last fallback's complete eight-control readbacks and boundary check passed without new mutations. Its later readback was after T0+600 and retained its own `deadlineMissed=true`; it does not erase the earlier on-time pause or repair the failed continuous tail. |
| Saved state | The actual post-apply raw state is serial94, 60 managed instances, hash `7bbb39cb…f1e2c`. Its outputs match the reviewed active plan; this describes Terraform's saved configuration, not the live API pause. Configuration convergence remains unproved. Never replace this file with serial85 or serial76. |

The fixed AWS CLI2.38.1 formatter was isolated locally with synthetic errors. Both enhanced and legacy errors use an `aws: [ERROR]:` prefix, which the old plain-text404 regular expression rejects. The original attempt's stderr/stdout were not retained, so this compatibility defect is reproduced without claiming the historical response was definitely404. Official source: [error handler](https://raw.githubusercontent.com/aws/aws-cli/2.38.1/awscli/errorhandler.py), [prefix formatter](https://raw.githubusercontent.com/aws/aws-cli/2.38.1/awscli/errorformat.py).

The checkpoint51 source fix adds `--cli-error-format json` only to HeadObject. Only exit254, empty stdout and a bounded UTF-8 JSON object with exactly `Code="404"` and `Message="Not Found"` becomes the existing absence result. Duplicate keys, nonfinite JSON, extra fields, warnings, malformed data,403, authentication failures and other service errors stay blocked. This is a service-error code check, not direct `ResponseMetadata` evidence. Failures record fixed diagnostic categories, output lengths and hashes; error bodies, environments and credentials are not logged. The same transport covers pre-upload absence and later incoming-source deletion verification. Positive200 metadata, three conditional seed rows, conditional `IfNoneMatch="*"` PUT and all identity/nonce/once/STOP/funding/deadline gates remain unchanged. No corrected runtime has been deployed or exercised against media.

## Inert repository snapshot: V15 proof chain with the V13 lifecycle

The candidate starts durable writer heartbeats before watchdog spawn, covers startup and subsequent writer work with cleanup, and bounds readiness within the **original** window: the earlier of T0+120 seconds and the original stop-reserve boundary. It retains full child identity/fresh ACK, STOP, funding, boundary, once-only, fixture and drain guards.

The original V13 candidate passed **9/9 injected-stub tests** and independent **static** review. Neither ran a real thread/process/CLI/SDK/signal/cloud path. Same-VM hangs, filesystem blocking and actual CloudShell/cloud latency remain unverified. Checkpoint51 retained the inert V13 driver and added the reviewed Head JSON fix. The current [V15 snapshot](../tools/c-runtime-controller/README.md) preserves that lifecycle and fixture, uses the reviewed two-worker S3 reader, and updates four proof functions for the genuine paused95 normal-plan PASS plus its route/dependency pins. Eight self-contained fixture transport tests and nine startup tests pass without CLI/SDK/network or real processes. AST fingerprints omit only optional empty fields for Python-version portability; all real structure, values and guard-change restrictions remain checked. Synthetic formatter examples and temporary synthetic fixture bytes are explicitly labelled; no original image or private runtime evidence is bundled.

`ARM_REVIEWED` remains **False**, the preparer pin is `None`, and all 60 actual pins remain pending. The ARMTrue RELEASE, consumed bindings, private logs, plans and state are excluded. The Linux CloudShell paths, current tools and runtime evidence are not completely bound; this snapshot must not be executed against cloud resources. Passing local tests does not authorize another attempt.

## Current operating state

The application remains paused: eight Lambda functions have reserved concurrency zero, queue mappings are disabled, the outbox rule is disabled, the media bucket has no incoming notification, and its data-deny policy is restored. API, signup, mail, Lex and scheduled processing remain disabled. Retained storage and logs may still consume credit; pausing does not guarantee a zero bill. The additional personal spending limit remains **A$0**.

The deployed AWS source revision recorded for these attempts is `40b5d5f603ef362b50ebe4c317772a53f9b24631`; this documentation/source-snapshot change is not a new cloud deployment. The later separately reviewed same-binary refresh-only reconciliation completed with zero resource actions and produced serial95 / `5de33593…fc5`, now the current raw checkpoint. The original serial94 and blocked review remain retained. Never overwrite95 with old94,85 or76 snapshots. State synchronization remains separate from current API-pause proof and Terraform configuration convergence; see the [checkpoint52 review](c-runtime-checkpoint52-review-20261025.md). Current deployed counts are **AWS 60 / GCP 13**.

GCP12 remains a historical successful metadata observation. The later GCP13 result at **08:01:43.040569 UTC** passed 41 metadata reads with no HTTP inference call; its92 native files were downloaded and individually hash-verified. The archive, observation and summary hashes are recorded in the selected evidence JSON; the raw files remain private and outside Git. Earlier operator model warmup HTTP 200 remains evidence only for that operator request, not Lambda WIF or automatic media processing. The new AWS CloudShell session passed its official root STS identity check and reported pinned-tool restoration/local validation success; these are tooling checks and do not establish application writes or a new runtime success.

## Retained evidence

| Record | SHA-256 |
|---|---|
| Consumed review packet | `e32597d74b57072f52dd7676bfd46a401e68726f9efac1d3ad80b8fcedbd8832` |
| Final controller binding used once | `870441458025caf926479a138b684b9f2d1f2ea82e6550090d13304b001b0f3f` |
| Actual state, serial 85 / 60 resources | `7b4d5aed8ce5fd253fceac940637c67554ec0dadea61ca5a352e44a03b455204` |
| Four-reducer operator recovery receipt | `6e73f4dcaaa38a6046250acf1403677cdccf2bf71609158f03fece1db5993cbb` |
| Independent all-eight post-check | `77b108c8610223d477f2fdff558781d10c2b2575f3e85d3a3d06c19b39db1b9d` |
| Original private archive, 678,913 bytes / 2,203 files | `05fad95ee8aa995cf4925605acd3b3e1c8663dc2e84ecb16a6db13356633f859` |
| Later failed read-only collection summary | `6069e2666fb0ecca94250231aa0b25708d8255b6fa562264296deeb6c1da11f1` |
| Attempt 2 native archive, 678,835 bytes / 1,835 payload files plus manifest | `7cac5658e60ec6099c2dc07144cceae8617e64c4d7495d4d36b09563f1bc9bae` |
| Attempt 2 final drain result | `0053842341a98eb1d2ebfbdd7acad05f559c4b3a5078398a815d50633542e457` |
| Attempt 2 exact-process/native-state closeout | `c4ea1f40683f6c51fd4733daefbc1f081dce01d125f66ed57f3d69128fa5f03f` |
| V13 upstream local nine-test receipt | `890cf4e4fbcf0b4f5ebd1cf3276368f09b8079d7de6a98ddf5f8b940a3c1a743` |
| V13 upstream independent static review | `84dc9a88b3471c625f9320319953e242c1e81f4b62a9f9b8859ccc5a36044d1f` |

The original archives and their file hashes were checked locally and are excluded from Git. The third-attempt final archive has 1,952 payload files and SHA `ea0215caae07f1d6dd8695ca5d5c047f00304b6860ffe36493510c865c988cd1`; selected hashes are retained in the status JSON, without raw state, logs or authority bodies. Only [selected nonsecret status/evidence hashes](../evidence/c-runtime-attempts-status-20261025.json) and the inert code snapshot enter this checkpoint. Screenshots C12/C13 are retained locally; the clean C13 image shows the actual 03:09 post-check record and is not a new API audit at screenshot time. No screenshots or raw runtime evidence are added to this commit.

## Work still required

1. Bind the separate current paused-API and supervisor proofs to the reconciled serial95 checkpoint and reviewed V15 candidate. The new unused a927 normal plan has passed its real native gate; consumed94c cannot be replayed. The Head JSON fix still has only local/static acceptance, and no fourth media attempt has begun.
2. Obtain fresh quota, funding, GCP, identity and supervisor evidence and present a concrete new single-use runtime scope. All three attempt authorities are consumed and cannot be replayed as a new approval.
3. Execute one actual image through the automatic AWS–GCP path, preserve real-role WIF/model READY evidence, and demonstrate timely pause/recovery plus the fixture-specific continuous observation tail and Terraform convergence. The 570-second paused-only observation does not replace this active-work acceptance.
4. Coordinate the remaining deployment security checks with B (final HTTPS-origin CORS and authenticated/anonymous/cross-user access) and the short real-cloud video cadence test with A/D. Existing personal anonymous Run 403 and earlier operator warmup need not be repeated just for screenshots; historical team-environment checks do not become current personal-environment passes.
5. Finalize the architecture, personal report and private team/staff repository handover from actual results. The personal report is draft 5, 389 words, and has passed layout review, but is not a final submission. GCP credit expiry was observed as 28 October; review retained resources by 27 October and agree assessment-week availability/funding without upgrading the A$0 personal-spend limit.

Vendor selection is AWS + GCP, permitted by Spec p2 and Rubric p7. Oracle is not mandatory. Single-image success would still not establish every team acceptance criterion, video processing, user-isolation testing, private repository access or availability through assessment.

No reliable completion percentage or completion time is currently asserted. Deployment and read-only checks must not be counted as successful application processing.
