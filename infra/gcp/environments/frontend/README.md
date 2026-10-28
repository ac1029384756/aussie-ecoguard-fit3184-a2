# Separate static HTTPS frontend deployment

Local preparation on 27 October passed native Terraform validation and five
mock tests. The linux/amd64 static image passed 17 actual local container checks
and rendered the sign-in UI in Chrome. Its verified image manifest is
`sha256:d12130aa3869398d68bf60d580db256e6abd99e7a6ffe2f5c71950d82709d458`.
It is not published or deployed yet. On 28 October the actual native cloud plan
passed the corrected local review: three creates, no updates or deletes. The
original gate failure and immutable plan were preserved; resolved project data
was in `prior_state`, rather than `planned_values`. See the
[saved-plan review](../../../../docs/c-frontend-saved-plan-review-20261028.md).
See [selected local evidence](../../../../evidence/c-frontend-local-20261027.json).

This root is prepared for review, not deployed by committing it. It creates only
the `ecoguard-frontend` service account, `ecoguard-web` Cloud Run service, and
that frontend's `allUsers` service-level invoker binding. It manages no project
IAM, private inference, AWS, API, signup, data access, registry or API enablement.
The existing Run API and image repository must already be available.

The backend `state/frontend.tfstate` is distinct from the personal inference
root. Use one state owner and retain its backups outside Git. Never initialize
this root over the existing 13-resource inference state or migrate that state.
The required `frontend_image` must reference this project's exact
`ecoguard/frontend@sha256:...` path; a missing image fails instead of proposing
an empty/default deployment. Both scaling limits are min0/max1, with one CPU,
256 MiB, request-based CPU and no startup boost. These limits are not a hard
spending cap. Credits/funding must remain valid through deployment and testing.

Build `apps/web` with development authentication false and the reviewed public
AWS API/pool/client identifiers. Prepare an isolated Docker build context with
only `dist/`, `nginx.conf` and the Dockerfile from `apps/web/deploy`. Pin the
official nginx linux/amd64 base digest. The container runs as UID/GID101, serves
SPA deep links, and keeps absent assets/API paths as errors. It contains no
password, token, `.env`, Terraform state or backend data. Google supplies HTTPS;
TLS is not terminated inside the container.

Prepare and review the actual saved plan using the verified image digest. Image
publication is not required to generate this plan, but must precede deployment:

```sh
terraform init -lockfile=readonly
terraform plan -input=false -out=frontend.tfplan \
  -var='frontend_image=us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/frontend@sha256:<reviewed-digest>'
terraform show -json frontend.tfplan > frontend.tfplan.json
python3 check_plan.py frontend.tfplan.json \
  --expected-image 'us-central1-docker.pkg.dev/ecoguard-fit3184-a2-2026/ecoguard/frontend@sha256:<reviewed-digest>'
```

The initial review must allow exactly three creates, no update/delete/import,
no drift, the fixed project/region, exact static image and service identity,
and only the frontend's public invoker grant. Preserve the actual plan/hash and
get the required action-time confirmation before that new public access is
applied through the browser. Recheck identity, existing private service IAM and
funding immediately before execution. Do not apply a changed or stale plan.

Then verify the actual HTTPS origin, health, all assets, SPA deep links and
login UI. These checks do not establish successful signup or API/media use.
Only after the URL is known should a separate AWS plan add its exact origin to
CORS and review the bounded API/signup test. Existing runtime/media permits
cannot be reused. Image retention and this new service require a reviewed
cleanup before credits expire; no automatic cleanup is provided here.
