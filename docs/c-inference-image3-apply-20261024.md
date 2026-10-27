# Image3 applied and configuration verified, 24 October 2026

The image-only saved plan applied **once, exit 0**, and its configuration postchecks passed at `2026-10-24T01:22:00.925557+00:00`. This is selected evidence from the parent agent's actual official CloudShell/UI observation. It is not a copy of the raw summary or an independent live check. See the [selected evidence](../evidence/c-inference-image3-apply-20261024.json); full state, plans, policies, logs and authorization remain private.

| Verified setting | Actual observation |
| --- | --- |
| Target | `ecoguard-fit3184-a2-2026` / `995070689587`, `us-central1` |
| Source | `ac7757717486b3db2da8c955ebffcc01f6807724` |
| Change | 1 service image update, 12 no-ops, 0 creates/deletes; 13 managed resources |
| State | Same lineage; serial `19 → 21`; SHA-256 `8fceea80600b2b02caea3402951d8f7954c975845b3503522be69b69f2881358` |
| Ready revision | `ecoguard-inference-00003-jwb` |
| Service URL | Unchanged: `https://ecoguard-inference-adlnb7yumq-uc.a.run.app` |
| Image digest | `sha256:f0b3dd5289159f84454afd9e0466e6151464fc8e5cb49a063102938437549a17` |
| Boundaries | Full IAM, enabled APIs, capacity and release source unchanged during apply |

The software change adapts the explicit private Cloud Run mode to platform token-header consumption. Oracle/local service-token verification and independent Cognito verification remain unchanged. The actual plan permitted only the image update. Its separate standing-task record used the user's existing finish-C/default-consent direction; it claimed no new human approval and reused no earlier plan authorization.

The retained apply summary SHA-256 is `2d7847731aa7b265e6b293fc1e9aff51826a04b5c729c0c577509ba54941693a`; its post-verification detail is `247c9ffaed655fb33338f72ddfd0c67110e4090cef253677d10f3b484f9415f2`. The companion JSON also pins the saved binary, frozen helpers, publication and apply-input manifest. Existing failed HTTP history, including the image2 warmup `401` response, remains preserved.

The apply helper made no application HTTP requests, model calls or AWS actions. This record establishes configuration and Ready-revision verification only. The separate warmup and any subsequent inference or cross-cloud acceptance require their own actual results; none is claimed here.

Additional personal-spend limit remains **A$0**. Existing credits expire **28 October**; review/cleanup is due by **27 October Melbourne**. No automatic cleanup is configured.

Prepared with Codex assistance.
