"""ASGI contract tests; platform IAM itself is outside this local fixture.

The Cloud Run cases simulate requests ALREADY admitted by a private IAM proxy.
Only synthetic test JWTs are used. No real network, cloud token, model download
or model execution occurs here.
"""
import asyncio
import json
import sys
import time
import unittest

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import CognitoVerifier, GoogleServiceVerifier
from app.main import create_app
from app.settings import Settings


class RecordingWorker:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"configured": True, "ready": False, "loadedModels": []}

    def run(self, operation, payload, cancelled):
        self.calls.append((operation, payload))
        return {"fixtureOperation": operation}

    def close(self):
        pass


class CloudRunIAMAdapterTests(unittest.TestCase):
    def settings(self, mode="cloud-run", service="private-cloud-run-service"):
        return Settings(service_auth_mode=mode, cloud_run_service=service,
                        local_service_token="unit-test-service-token-32-characters-long",
                        cognito_issuer="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST",
                        cognito_client_id="test-client",
                        service_token_audience="https://oracle.example.test",
                        service_token_email="invoker@test-project.iam.gserviceaccount.com")

    def test_private_platform_request_survives_consumed_service_header(self):
        worker = RecordingWorker()
        with TestClient(create_app(self.settings(), worker=worker)) as client:
            response = client.post("/v1/warmup", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"fixtureOperation": "warmup"})
        self.assertEqual(worker.calls, [("warmup", {})])
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("transformers", sys.modules)

    def test_cloud_run_mode_without_platform_environment_fails_closed(self):
        worker = RecordingWorker()
        with TestClient(create_app(self.settings(service=""), worker=worker)) as client:
            for headers in ({}, {"X-Serverless-Authorization": "Bearer invented-platform-token"}):
                response = client.post("/v1/warmup", headers=headers)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["error"]["code"], "SERVICE_AUTH_NOT_CONFIGURED")
        self.assertEqual(worker.calls, [])

    def test_local_and_oracle_missing_or_bad_bearers_remain_unauthorized(self):
        def no_network(request):
            raise AssertionError("Malformed/missing tokens must not fetch signing keys")

        for mode in ("local", "oracle"):
            # Oracle must not trust even an injected platform service name.
            settings = self.settings(mode, "injected-name" if mode == "oracle" else "")
            worker = RecordingWorker()
            network = httpx.AsyncClient(transport=httpx.MockTransport(no_network))
            try:
                verifier = GoogleServiceVerifier(settings, network)
                with TestClient(create_app(settings, worker=worker, service_verifier=verifier)) as client:
                    for headers in ({}, {"X-Serverless-Authorization": "Bearer bogus-platform-token"}):
                        response = client.post("/v1/warmup", headers=headers)
                        self.assertEqual(response.status_code, 401, mode)
                self.assertEqual(worker.calls, [])
            finally:
                asyncio.run(network.aclose())

    def test_local_secret_is_rejected_when_platform_environment_is_present(self):
        settings = self.settings("local")
        worker = RecordingWorker()
        with TestClient(create_app(settings, worker=worker)) as client:
            response = client.post("/v1/warmup", headers={
                "X-Serverless-Authorization": "Bearer " + settings.local_service_token})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(worker.calls, [])

    def test_cloud_run_query_still_requires_a_valid_cognito_access_token(self):
        settings, worker = self.settings(), RecordingWorker()
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
        public.update(kid="iam-adapter-test", alg="RS256", use="sig")
        calls = []

        def jwks(request):
            calls.append(str(request.url))
            self.assertEqual(str(request.url), settings.cognito_issuer + "/.well-known/jwks.json")
            return httpx.Response(200, json={"keys": [public]})

        network = httpx.AsyncClient(transport=httpx.MockTransport(jwks))
        try:
            verifier = CognitoVerifier(settings, network)

            def token(**overrides):
                claims = {"iss": settings.cognito_issuer, "client_id": settings.cognito_client_id,
                          "sub": "user-123", "token_use": "access", "exp": int(time.time()) + 120,
                          "iat": int(time.time()) - 2}
                claims.update(overrides)
                return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "iam-adapter-test"})

            with TestClient(create_app(settings, worker=worker, verifier=verifier)) as client:
                body = {"requestId": "private-iam-query", "purpose": "pet"}
                for authorization in (None, "Bearer invalid-user-token", "Bearer " + token(client_id="wrong-client")):
                    headers = {} if authorization is None else {"Authorization": authorization}
                    self.assertEqual(client.post("/v1/query-authorizations", json=body, headers=headers).status_code, 401)
                valid = client.post("/v1/query-authorizations", json=body,
                                    headers={"Authorization": "Bearer " + token()})
                self.assertEqual(valid.status_code, 200)
                self.assertEqual(valid.json(), {"sub": "user-123", "requestId": "private-iam-query"})
            self.assertTrue(calls)
            self.assertEqual(worker.calls, [])
            self.assertNotIn("torch", sys.modules)
        finally:
            asyncio.run(network.aclose())


if __name__ == "__main__":
    unittest.main()
