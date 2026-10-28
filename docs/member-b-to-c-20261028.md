# B to C frontend handoff - 28 October 2026

## Version identity

At the time of the initial handoff the B frontend changes were uncommitted on
local branch `Jiarui/main`, whose then-current commit `f9a9e7a` does not contain
them. The PR containing this document is the reviewable source of the changes;
its base is the team's current `Jiarui/main`. The earlier accompanying source
archive is a snapshot for review, not a replacement for the team's contribution
history. Check the PR status before assuming these changes have been merged.

## Configuration supplied by C

- AWS region: `us-east-1`
- API base: `https://0gbw8hhmo9.execute-api.us-east-1.amazonaws.com/api/v1`
- Cognito pool: `us-east-1_Sog8ekMM1`
- Cognito app client: `5gu7g1rgkmabdd551h5k3350f6`, without a client secret
- Production build must use `VITE_DEV_MODE=false`.

These values are public browser configuration, not passwords or AWS credentials.
An ignored `apps/web/.env.production.local` has been prepared locally. It is not
included in the source archive. Set the four Vite values in C's build environment
or an ignored production env file **before** running `npm run build`; they are
embedded into the static build.

## Deployment status reported by C

The API and public sign-up remain paused. The HTTPS frontend is not published.
Allowed CORS origins currently include only `http://localhost:5173` and
`http://127.0.0.1:5173`. The final HTTPS origin must be configured by C before
end-to-end acceptance. These statements are C's report, not a fresh AWS inspection.
No AWS calls, registration, email confirmation, sign-in or deployment were
performed for this handoff.

## Included B work

- Authentication forms, temporary-password/code flows, pending-operation guards,
  and session-expiry fixes, including non-JSON 401 responses and stale async reads.
- English date/time controls for uploads and searches and English file-picker
  buttons, with narrow-screen adjustments.
- Authentication and date regression tests, user guide and local evidence.
- 52 frontend tests and the production build passed on 26 October. The 28 October
  build preparation checks the new public configuration; it does not constitute
  cloud acceptance.

## Integration

1. Review this PR's `apps/web` changes against the team's latest branch. Preserve
   C's environment configuration and any concurrent changes. Existing package
   manifests/lockfile were not changed.
2. Install dependencies with `npm ci` in `apps/web` and set the Vite values above.
3. Run `npm test -- --run` and `npm run build`. The pet-result contract test also
   needs the repository's Python environment and existing backend source.
4. Publish `apps/web/dist` only when the team authorizes deployment. Configure SPA
   fallback for `/media`, `/search`, `/pets` and `/subscriptions`, and the final
   HTTPS origin in the applicable CORS policies.
5. Notify B when authentication and API access are open and verified. B then
   performs real registration/mailbox/sign-in/session tests and positive workflow
   checks against A/C/D's deployed services. Account holders enter their own
   passwords and verification codes.

The archive intentionally excludes `.git`, `.env*`, dependencies, build output,
credentials, Terraform state and real user media. `.env.example` is included as
the generic template. Local evidence is labelled development-only.
