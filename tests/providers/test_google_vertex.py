from __future__ import annotations as _annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from inline_snapshot import snapshot

from ..conftest import try_import

with try_import() as imports_successful:
    from google.auth.transport.requests import Request

    from pydantic_ai.providers.google_vertex import GoogleVertexProvider

pytestmark = [
    pytest.mark.skipif(not imports_successful(), reason='google-genai not installed'),
    pytest.mark.anyio(),
]


@pytest.fixture()
def http_client():
    async def handler(request: httpx.Request):
        if (
            request.url.path
            == '/v1/projects/my-project-id/locations/us-central1/publishers/google/models/gemini-1.0-pro:generateContent'
        ):
            return httpx.Response(200, json={'content': 'success'})
        raise NotImplementedError(f'Unexpected request: {request.url!r}')  # pragma: no cover

    return httpx.AsyncClient(transport=httpx.MockTransport(handler=handler))


def test_google_vertex_provider(allow_model_requests: None) -> None:
    provider = GoogleVertexProvider()
    assert provider.name == 'google-vertex'
    assert provider.base_url == snapshot(
        'https://us-central1-aiplatform.googleapis.com/v1/projects/None/locations/us-central1/publishers/google/models/'
    )
    assert isinstance(provider.client, httpx.AsyncClient)


@dataclass
class NoOpCredentials:
    token = 'my-token'

    def refresh(self, request: Request): ...


@patch('pydantic_ai.providers.google_vertex.google.auth.default', return_value=(NoOpCredentials(), 'my-project-id'))
async def test_google_vertex_provider_auth(allow_model_requests: None, http_client: httpx.AsyncClient):
    provider = GoogleVertexProvider(http_client=http_client)
    await provider.client.post('/gemini-1.0-pro:generateContent')
    assert provider.region == 'us-central1'
    assert getattr(provider.client.auth, 'project_id') == 'my-project-id'
    assert getattr(provider.client.auth, 'token_created') is not None


async def test_google_vertex_provider_service_account_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, allow_model_requests: None
):
    service_account_path = tmp_path / 'service_account.json'
    save_service_account(service_account_path, 'my-project-id')

    provider = GoogleVertexProvider(service_account_file=service_account_path)
    monkeypatch.setattr(provider.client.auth, '_refresh_token', lambda: 'my-token')
    await provider.client.post('/gemini-1.0-pro:generateContent')
    assert provider.region == 'us-central1'
    assert getattr(provider.client.auth, 'project_id') == 'my-project-id'
    assert getattr(provider.client.auth, 'token_created') is not None


def save_service_account(service_account_path: Path, project_id: str) -> None:
    service_account = {
        'type': 'service_account',
        'project_id': project_id,
        'private_key_id': 'abc',
        # this is just a random private key I created with `openssl genpke ...`, it doesn't do anything
        'private_key': (
            '-----BEGIN PRIVATE KEY-----\n'
            'MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAMFrZYX4gZ20qv88\n'
            'jD0QCswXgcxgP7Ta06G47QEFprDVcv4WMUBDJVAKofzVcYyhsasWsOSxcpA8LIi9\n'
            '/VS2Otf8CmIK6nPBCD17Qgt8/IQYXOS4U2EBh0yjo0HQ4vFpkqium4lLWxrAZohA\n'
            '8r82clV08iLRUW3J+xvN23iPHyVDAgMBAAECgYBScRJe3iNxMvbHv+kOhe30O/jJ\n'
            'QiUlUzhtcEMk8mGwceqHvrHTcEtRKJcPC3NQvALcp9lSQQhRzjQ1PLXkC6BcfKFd\n'
            '03q5tVPmJiqsHbSyUyHWzdlHP42xWpl/RmX/DfRKGhPOvufZpSTzkmKWtN+7osHu\n'
            '7eiMpg2EDswCvOgf0QJBAPXLYwHbZLaM2KEMDgJSse5ZTE/0VMf+5vSTGUmHkr9c\n'
            'Wx2G1i258kc/JgsXInPbq4BnK9hd0Xj2T5cmEmQtm4UCQQDJc02DFnPnjPnnDUwg\n'
            'BPhrCyW+rnBGUVjehveu4XgbGx7l3wsbORTaKdCX3HIKUupgfFwFcDlMUzUy6fPO\n'
            'IuQnAkA8FhVE/fIX4kSO0hiWnsqafr/2B7+2CG1DOraC0B6ioxwvEqhHE17T5e8R\n'
            '5PzqH7hEMnR4dy7fCC+avpbeYHvVAkA5W58iR+5Qa49r/hlCtKeWsuHYXQqSuu62\n'
            'zW8QWBo+fYZapRsgcSxCwc0msBm4XstlFYON+NoXpUlsabiFZOHZAkEA8Ffq3xoU\n'
            'y0eYGy3MEzxx96F+tkl59lfkwHKWchWZJ95vAKWJaHx9WFxSWiJofbRna8Iim6pY\n'
            'BootYWyTCfjjwA==\n'
            '-----END PRIVATE KEY-----\n'
        ),
        'client_email': 'testing-pydantic-ai@pydantic-ai.iam.gserviceaccount.com',
        'client_id': '123',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
        'client_x509_cert_url': 'https://www.googleapis.com/...',
        'universe_domain': 'googleapis.com',
    }

    service_account_path.write_text(json.dumps(service_account, indent=2))
