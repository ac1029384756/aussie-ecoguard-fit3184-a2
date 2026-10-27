# First private HTTPS attempt: retained 404, 24 October 2026

The private service configuration had passed its complete audit. The first bounded application request was anonymous `GET /healthz`: **404**, 1,568 response bytes, 0.045 seconds. The checker stopped before obtaining a user token, authenticated requests or model warmup. Its read-only postcheck verified unchanged state, release source and IAM at `2026-10-23T23:32:07.146983Z`.

This is **not verified IAM rejection**. The original result and private files remain unchanged; no request has been retried. See [actual selected evidence](../evidence/c-private-http-first-attempt-20261024.json).

Read-only queries found zero Cloud Run request records and zero matching HttpIngress policy records for the diagnostic interval. Absence of records alone does not establish the cause. Google's [known issues](https://docs.cloud.google.com/run/docs/known-issues) describe reserved URL paths, including some ending in `z`, and recommend avoiding that suffix. The deployed application exposes `/healthz` and `/readyz`, with no non-z alias. This is a plausible platform-path conflict, not a proven sole root cause.

The corrective source work adds `/health` and `/ready` while retaining the legacy local/Oracle paths. A new immutable image and a narrowly reviewed existing-service update are required before those aliases exist in Cloud Run. Neither permission broadening nor a capacity increase is part of that repair. Further HTTP outcomes must identify their actual revision/path and preserve this failure; do not relabel it as a passing anonymous-access test.

AWS remains paused. Real cloud model loading, AWS-role federation and media inference are unverified. Prepared with Codex assistance.
