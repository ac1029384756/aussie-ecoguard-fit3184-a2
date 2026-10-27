"""Strict public WIF document checks for C's new personal deployment.

These checks describe the intended identity. They do not contact either cloud,
create trust, resolve credentials or prove that the referenced resources exist.
"""

import json


PROJECT = "ecoguard-fit3184-a2-2026"
PROJECT_NUMBER = "995070689587"
INVOKER = f"ecoguard-aws-invoker@{PROJECT}.iam.gserviceaccount.com"
AUDIENCE = (f"//iam.googleapis.com/projects/{PROJECT_NUMBER}/locations/global/"
            "workloadIdentityPools/ecoguard-aws/providers/aws-role")
CREDENTIAL_SOURCE = {
    "environment_id": "aws1",
    "region_url": "http://169.254.169.254/latest/meta-data/placement/availability-zone",
    "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials",
    "regional_cred_verification_url": "https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15",
}
MAX_DOCUMENT_BYTES = 16 * 1024


def validate_personal_wif(document):
    """Reject other projects, secrets and configurable file/URL/executable sources."""
    required = {
        "type": "external_account",
        "audience": AUDIENCE,
        "subject_token_type": "urn:ietf:params:aws:token-type:aws4_request",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": CREDENTIAL_SOURCE,
    }
    optional = {
        "universe_domain": "googleapis.com",
        "service_account_impersonation_url": (
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{INVOKER}:generateAccessToken"),
    }
    if (not isinstance(document, dict)
            or not set(required) <= set(document) <= set(required) | set(optional)
            or any(document.get(key) != value for key, value in required.items())
            or any(document[key] != value for key, value in optional.items() if key in document)):
        raise ValueError("WIF must use the reviewed personal Google project and fixed AWS metadata source")
    return document


def parse_personal_wif(value):
    """Parse a bounded JSON document without permitting duplicate keys."""
    if len(value.encode("utf-8") if isinstance(value, str) else value) > MAX_DOCUMENT_BYTES:
        raise ValueError("WIF document is too large")

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("WIF contains duplicate JSON keys")
            result[key] = item
        return result

    return validate_personal_wif(json.loads(value, object_pairs_hook=unique_object))
