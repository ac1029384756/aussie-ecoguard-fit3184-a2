# D work package handover - 27 October 2026

Owner identity for this contribution: GitHub `ac1029384756`. Replace this with the student's name
and ID in the final contribution table after the team confirms them.

## What I implemented

- Strengthened the existing notification worker so an SNS email confirmation becomes active during
  delivery processing. A user no longer has to return to the subscriptions page and manually refresh
  before the first matching alert can be sent.
- Added a final delayed-delivery guard for subscription status, media ACL, generation, record version,
  and current tag intersection immediately before SNS publish.
- Improved the email body with the exact matched monitored tags and the stable authenticated media
  page link.
- Added focused Lex acceptance tests for required-slot elicitation, species/count search, clickable
  result links, server-bound result IDs, public-only lost-pet retrieval, and invalid-count handling.
- Added notification positive/negative tests for pending/confirmed channels, cancelled subscriptions,
  unmatched tags, replay protection, matched-tag content, and stable links.
- Prepared an independent 50-case acceptance dataset manifest and a D-specific demo/evidence runbook.

## Verification level

The new work is locally verified with deterministic fixtures. It does not claim a deployed Lex bot,
real SNS delivery, production media, model accuracy, or complete assignment acceptance. Cloud tests
remain subject to the repository's A$0 extra-spend rule and require a separately reviewed activation
of the existing personal AWS environment.

Run the focused checks from the repository root:

```bash
python3 -m unittest \
  tests.backend.test_backend.BackendTest.test_notification_confirmation_refresh_does_not_depend_on_ui \
  tests.backend.test_backend.BackendTest.test_notification_pending_confirmation_does_not_publish \
  tests.backend.test_backend.BackendTest.test_notification_negative_cases_do_not_publish \
  tests.backend.test_backend.BackendTest.test_lex_elicits_species_and_returns_clickable_authorized_results \
  tests.backend.test_backend.BackendTest.test_lex_lost_pet_search_excludes_private_sightings \
  tests.backend.test_backend.BackendTest.test_lex_invalid_count_fails_safely -v
```

## Text for the team report contribution table

> Implemented and independently tested the Part D Lex and notification acceptance path. Improved SNS
> confirmation handling so delivery does not depend on a UI refresh, added delayed-event ACL/version/
> tag revalidation, and included matched tags in alert emails. Added Lex tests for slot elicitation,
> tag/count queries, public-only lost-pet results, clickable links, and invalid input. Prepared the
> 50-case independent dataset manifest, evidence checklist, and live-demo recovery runbook. Real cloud
> Lex/SNS acceptance remains pending a reviewed deployment window.

## Remaining cloud acceptance

1. Review the Terraform plan for the existing personal AWS account and confirm current credits before
   enabling anything. Do not resume the course Lab or deploy from this document.
2. Deploy/publish the formal Lex bot and alias, bind the exact fulfillment Lambda permission, and run
   an authenticated web conversation against real indexed media.
3. Confirm the controlled test mailbox with SNS; capture one matching upload/update delivery and the
   required no-send cases.
4. Populate the dataset manifest with licensed assets and SHA-256 values, execute all 50 cases, and
   retain failures in the reported denominator.
5. Update `docs/acceptance-matrix.md` only with timestamped evidence from the deployed commit.
