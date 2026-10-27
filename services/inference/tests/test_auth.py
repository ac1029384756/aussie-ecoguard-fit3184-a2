import asyncio
import sys
import time
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import CognitoVerifier
from app.errors import ServiceError
from app.main import create_app


def verifier_for(settings, keys):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [keys[1]]}))
    return CognitoVerifier(settings, httpx.AsyncClient(transport=transport))


async def test_real_rsa_signature_and_claims(settings, keys, token_factory):
    verifier = verifier_for(settings, keys)
    assert await verifier.verify("Bearer " + token_factory()) == "user-123"
    assert verifier.keys
    await verifier.client.aclose()


@pytest.mark.parametrize("claims", [
    {"token_use": "id"}, {"client_id": "another-client"}, {"exp": 1},
    {"iss": "https://evil.example/issuer"}, {"iat": 4102444800}, {"sub": ""},
])
async def test_reject_wrong_or_expired_user_token(settings, keys, token_factory, claims):
    verifier = verifier_for(settings, keys)
    with pytest.raises(ServiceError, match="invalid or expired"):
        await verifier.verify("Bearer " + token_factory(**claims))
    await verifier.client.aclose()


async def test_tampered_signature_fails(settings, keys, token_factory):
    verifier = verifier_for(settings, keys)
    token = token_factory()
    header, payload, signature = token.split(".")
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(ServiceError) as error:
        await verifier.verify(f"Bearer {header}.{payload}.{signature}")
    assert error.value.status == 401
    await verifier.client.aclose()


def test_dual_header_query_does_not_load_torch(settings, keys, token_factory):
    verifier = verifier_for(settings, keys)
    with TestClient(create_app(settings, verifier=verifier)) as client:
        body = {"requestId": "query-123", "purpose": "pet"}
        good = {"X-Serverless-Authorization": "Bearer " + settings.local_service_token,
                "Authorization": "Bearer " + token_factory()}
        assert client.post("/v1/query-authorizations", json=body).status_code == 401
        assert client.post("/v1/query-authorizations", json=body, headers={"Authorization": good["Authorization"]}).status_code == 401
        assert client.post("/v1/query-authorizations", json=body, headers={"X-Serverless-Authorization": good["X-Serverless-Authorization"]}).status_code == 401
        result = client.post("/v1/query-authorizations", json=body, headers=good)
        assert result.status_code == 200
        assert result.json() == {"sub": "user-123", "requestId": "query-123"}
        assert "torch" not in sys.modules
        assert client.get("/readyz").status_code == 503
        assert client.get("/healthz").json()["models"]["loadedModels"] == []
        assert client.post("/v1/query-authorizations", json={**body, "ownerSub": "forged"}, headers=good).status_code == 422


def test_local_service_mode_forbidden_in_cloud_run(settings, keys, token_factory):
    cloud_settings = replace(settings, cloud_run_service="real-cloud-run-service")
    headers = {"X-Serverless-Authorization": "Bearer " + settings.local_service_token,
               "Authorization": "Bearer " + token_factory()}
    with TestClient(create_app(cloud_settings, verifier=verifier_for(settings, keys))) as client:
        assert client.post("/v1/query-authorizations", json={"requestId": "q1", "purpose": "file"}, headers=headers).status_code == 401


def test_probe_aliases_preserve_model_readiness_without_authorizing_work(settings):
    class StatusWorker:
        ready = False

        def status(self):
            return {"configured": True, "manifestVersion": "probe-fixture", "ready": self.ready,
                    "loadedModels": ["detector", "embedding"] if self.ready else []}

        def run(self, *args):
            raise AssertionError("Probe requests and unauthorized warmup must not execute model work")

        def close(self):
            pass

    worker = StatusWorker()
    with TestClient(create_app(settings, worker=worker)) as client:
        for ready in (False, True):
            worker.ready = ready
            health, legacy_health = client.get("/health"), client.get("/healthz")
            assert health.status_code == legacy_health.status_code == 200
            assert health.json() == legacy_health.json() == {"status": "alive", "schemaVersion": "1", "models": worker.status()}
            readiness, legacy_readiness = client.get("/ready"), client.get("/readyz")
            assert readiness.status_code == legacy_readiness.status_code == (200 if ready else 503)
            assert readiness.json() == legacy_readiness.json() == {"schemaVersion": "1", **worker.status()}
            assert client.post("/v1/warmup").status_code == 401
        assert "torch" not in sys.modules
        assert "transformers" not in sys.modules
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404


def test_authorization_deadline_is_bounded(settings):
    class SlowVerifier:
        async def verify(self, token):
            await asyncio.sleep(2)
            return "never-used"
    settings = replace(settings, authorization_timeout=0.05)
    with TestClient(create_app(settings, verifier=SlowVerifier())) as client:
        started = time.monotonic()
        result = client.post("/v1/query-authorizations", json={"requestId": "q1", "purpose": "file"},
                             headers={"X-Serverless-Authorization": "Bearer " + settings.local_service_token})
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "AUTHORIZATION_TIMEOUT"
        assert time.monotonic() - started < 1
