# C/B integration preflight, 27 October 2026

The current shared frontend can be prepared without waiting for another B
commit. Its local tests and production build pass. Online acceptance remains
blocked by the intentionally paused API/signup and the missing HTTPS frontend;
no runtime or data-access setting was changed by this checkpoint.

## Code available to the team

At the initial 11:45 UTC read, the upstream repository
`Jerry2003826/aussie-ecoguard-fit3184-a2` had one
branch, `Jiarui/main`, at `f9a9e7a7fba7dae1b4534820527d132b6fb3a985`.
Its last push is recorded as 13 October. Its `apps/web` tree exactly matches the
local checkpoint52 tree, `e346eb49fca3272f9234c11c1ff0988fe2cd4bc4`.
The only visible public fork is C's `xihan-u/aussie-ecoguard-fit3184-a2`, and
the only open upstream PR is C's draft PR #1. No newer B version was visible
there. This does not establish whether B has unpushed work or another private
or separately named repository. If so, its repository, branch or commit is
needed before deploying that version; it is not needed for C's independent
configuration and deployment preparation.

At the final readback, **Jerry2003826 had merged C's PR #1 at 11:50:03 UTC**
on 27 October. The upstream `Jiarui/main` head became
`00fd4ee1742113176abc88f21bd492e9ac50920f`. Its full source tree exactly
matches C's published checkpoint52, so this is a squash merge of the existing
C work, not a newer B frontend. The frontend tree remains unchanged and the
39 local test results still apply to it. C merged this upstream commit into
the working branch before publishing the preflight follow-up, preserving the
team's history and avoiding a repeat PR for the already merged source.

## Completed checks

- Installed frontend dependencies with the lockfile unchanged and install
  scripts disabled, using the verified local Node 22.23.4 tool.
- Ran all 39 frontend tests across eight files successfully. The first run
  failed because the repository-root Python environment was absent; after
  creating an ignored standard-library-only environment, all cases passed.
  That contract fixture used Python 3.14.7 locally, not the Lambda runtime.
- Built the production frontend with development authentication disabled and
  the public configuration below. TypeScript and Vite completed successfully.
  Six static files were packaged locally; nothing was deployed by this step.
- Performed identity-checked, read-only AWS configuration calls. The API and
  signup controls remain paused. The browser client has no secret, and the
  API JWT issuer/audience match its pool/client. No user, token, email, media,
  inference request or cloud resource mutation was created.

## Connection details and present limits

| Item | Verified value / status |
|---|---|
| AWS region | `us-east-1` |
| Cognito User Pool | `us-east-1_Sog8ekMM1` |
| Browser App Client | `5gu7g1rgkmabdd551h5k3350f6`, no client secret |
| API base | `https://0gbw8hhmo9.execute-api.us-east-1.amazonaws.com/api/v1` |
| Request authentication | `Authorization: Bearer <Cognito access token>`; JWT authorizer configured |
| API availability | Default execute-api endpoint disabled; the address is configuration, not a working online test environment |
| Public signup | Disabled (`AllowAdminCreateUserOnly=true`); email is an auto-verified attribute when signup is permitted |
| Current CORS origins | `http://localhost:5173`, `http://127.0.0.1:5173` |
| Deployed HTTPS frontend | None confirmed |

The selected records are in
[the preflight evidence](../evidence/c-b-preflight-20261027.json). AWS results
were read from visible CloudShell JSON output; the original raw command files
were not downloaded for this checkpoint. No browser authentication or complete
cloud application test is inferred from those configuration reads.

## Next execution boundary

The next online increment needs a reviewed HTTPS frontend deployment and its
exact CORS origin, current funding and pause/recovery proofs, and a concrete
bounded activation/test scope. Existing single-image permits were already
consumed; this preflight grants no replacement. B's unpushed changes, if any,
are needed for acceptance of that version rather than for C's preparation.

The refreshed GCP credit table displayed a positive remaining Free Trial credit,
an end date of **28 October 2026**, and **Expiring in 0 days**. The exact expiry
instant was not established. No billing upgrade or new billable deployment was
performed. The additional personal-spend limit remains A$0. Review funding and
retained-resource cleanup before another online increment.

Real end-to-end image/WIF successes remain **0**. The earlier failed attempts,
pause timing and observation gaps remain as recorded in the
[runtime history](c-runtime-attempt-and-recovery-20261025.md).
