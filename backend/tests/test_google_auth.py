import asyncio

import pytest

from app.auth import google


class FakeCertificatesResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, list[dict[str, str]]]:
        return {"keys": [{"kid": "google-key", "use": "sig"}]}


class FakeGoogleClient:
    async def __aenter__(self) -> "FakeGoogleClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str) -> FakeCertificatesResponse:
        assert url == google.GOOGLE_CERTS_ENDPOINT
        return FakeCertificatesResponse()


@pytest.mark.parametrize(
    ("claim_override", "valid"),
    [
        ({}, True),
        ({"iss": "https://attacker.example"}, False),
        ({"aud": "another-google-client"}, False),
        ({"nonce": "another-nonce"}, False),
        ({"email_verified": False}, False),
        ({"sub": ""}, False),
    ],
)
def test_google_credential_verifies_audience_issuer_nonce_and_email(
    monkeypatch: pytest.MonkeyPatch,
    claim_override: dict[str, object],
    valid: bool,
) -> None:
    monkeypatch.setattr(google.settings, "google_client_id", "expected-client")
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": "expected-client",
        "nonce": "expected-nonce",
        "sub": "google-user-id",
        "email": "customer@example.test",
        "email_verified": True,
    }
    claims.update(claim_override)
    monkeypatch.setattr(
        google.jwt,
        "get_unverified_header",
        lambda token: {"kid": "google-key"},
    )

    def decode(token, key, algorithms, options):
        assert key == {"kid": "google-key", "use": "sig"}
        assert algorithms == ["RS256"]
        assert options == {"verify_aud": False, "verify_iss": False}
        return claims

    monkeypatch.setattr(google.jwt, "decode", decode)
    monkeypatch.setattr(
        google.httpx, "AsyncClient", lambda **kwargs: FakeGoogleClient()
    )

    if valid:
        result = asyncio.run(
            google.verify_google_credential("signed-google-credential", "expected-nonce")
        )
        assert result["sub"] == "google-user-id"
    else:
        with pytest.raises(google.GoogleOAuthError):
            asyncio.run(
                google.verify_google_credential(
                    "signed-google-credential", "expected-nonce"
                )
            )
