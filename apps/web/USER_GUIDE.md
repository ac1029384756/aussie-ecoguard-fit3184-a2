# EcoGuard web user guide

## Open the application

Use the HTTPS application address supplied by the deployment owner. Registration,
sign-in and email confirmation use AWS Cognito. The frontend requires a Cognito
user pool, an app client without a client secret, and a reachable API. A local
development identity does not verify these cloud features.

1. Select **Create an account**. Enter email, first name, last name and password.
2. Enter the code delivered to that email and select **Verify email**. Use
   **Resend verification code** if necessary. Return to sign-in after confirmation.
3. Sign in. An invited account may require a permanent password and name details;
   an account with a configured code challenge requests that code next.
4. Use **Forgot password?** to request a reset code. Complete the code and new
   password fields yourself. Never share passwords or codes in screenshots.
5. Use **Sign out** beside the account name to leave. A rejected or expired
   session returns to the authentication screen and requires sign-in again.

## Save and manage sightings

Open **My media → Add a sighting**. Choose up to ten JPEG, PNG, WebP or MP4 files.
Images must be at most 20 MB; videos at most 100 MB and two minutes. Choose private
or community visibility and optionally enter the observation time in local time.
The English calendar provides month/year selection and a 24-hour time selector.
Use **Clear** to leave an optional date empty and **Done** to close the calendar.
Select **Upload & identify**. Content checksums identify duplicate files, including
renamed duplicates. **Already in your library** means no second record is needed.

Uploading and processing are separate stages. Follow processing in the library or
media details. A failure shows its cause; use **Retry processing** after the
underlying service is restored. Closing the upload dialog after upload does not
cancel server processing. A development environment without an entry model shows
a real configuration failure rather than invented animal tags.

Select media checkboxes for **Edit tags** or **Delete**. Tag editing supports
addition and removal. Deletion asks for confirmation; **Cancel** leaves files
unchanged. A deletion request is complete only after storage and record cleanup.
Open a media card to inspect its original, counts, tags and visibility. Media
links and thumbnails require an authorized account and successful processing.

## Search

- **Explore sightings → Species & counts:** add species and minimum counts. Every
  condition must match (AND). Optionally filter media type and observation dates.
  An empty result is distinct from a service error.
- **Search by a file:** choose a temporary query image or video. It does not become
  a normal library sighting. Follow the query status; retry recoverable failures.
- **Thumbnail lookup:** paste a thumbnail URL issued by this application to resolve
  its original. Arbitrary external URLs are not supported.
- **Find a pet:** supply a photo, a description, or both, then choose a time window.
  Results are possible public sightings, not confirmed pet identities. A service
  failure preserves the input so it can be retried.

## Chat and email alerts

Open **Ask EcoGuard**, enter a species/date/count question, and send it. The
production service uses AWS Lex. Open matching result links to inspect media.
Escape closes the chat panel. Failed sends preserve the message for another try.
An unconfigured Lex service displays an error instead of a simulated answer.

Under **Email alerts**, enter comma-separated tags and choose **Create alert**.
Confirm the separate AWS Notifications email channel, then use **Refresh email
status**. Cognito email verification and notification confirmation are separate.
Cancel an alert through its confirmation dialog. Production delivery must be
verified using an accessible test mailbox and the deployed notification service.

## Local development and evidence

Follow README.md for configuration. `VITE_DEV_MODE=true` is restricted to loopback;
the API must independently run in local mode. Alice and Bob use isolated in-memory
records. Restarting the local API discards those records. The development banner
must stay visible when collecting local screenshots.

Use the mobile navigation button on narrow screens. Keyboard users can use the
skip link, labelled fields and modal controls. Errors appear beside the workflow;
network/service errors must not be described as successful cloud acceptance.
