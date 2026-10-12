from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from ..config import settings

GOOGLE_CERTS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleOAuthError(RuntimeError):
    """Raised when Google OAuth cannot be securely completed."""


def google_sign_in_configured() -> bool:
    return bool(settings.google_client_id)


async def verify_google_credential(
    identity_token: str, expected_nonce: str
) -> dict[str, Any]:
    if not google_sign_in_configured():
        raise GoogleOAuthError("Google Sign-In is not configured.")
    timeout = httpx.Timeout(10, connect=5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            certificates_response = await client.get(GOOGLE_CERTS_ENDPOINT)
            certificates_response.raise_for_status()
            certificate_payload = certificates_response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise GoogleOAuthError("Google Sign-In could not be completed.") from error
    if not isinstance(certificate_payload, dict):
        raise GoogleOAuthError("Google returned invalid signing certificates.")
    certificates = certificate_payload.get("keys")
    if not isinstance(certificates, list) or not all(
        isinstance(certificate, dict) for certificate in certificates
    ):
        raise GoogleOAuthError("Google returned invalid signing certificates.")

    try:
        header = jwt.get_unverified_header(identity_token)
        key_id = header.get("kid")
        key = next(
            item
            for item in certificates
            if item.get("kid") == key_id and item.get("use", "sig") == "sig"
        )
        claims = jwt.decode(
            identity_token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
        if not isinstance(claims, dict):
            raise GoogleOAuthError("Google returned an invalid identity token.")
    except GoogleOAuthError:
        raise
    except (JWTError, StopIteration, TypeError, ValueError) as error:
        raise GoogleOAuthError("Google returned an invalid identity token.") from error

    audiences = claims.get("aud")
    valid_audience = (
        audiences == settings.google_client_id
        if isinstance(audiences, str)
        else isinstance(audiences, list)
        and settings.google_client_id in audiences
        and (len(audiences) == 1 or claims.get("azp") == settings.google_client_id)
    )
    if (
        claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com")
        or not valid_audience
        or claims.get("nonce") != expected_nonce
        or not isinstance(claims.get("sub"), str)
        or not claims.get("sub")
        or not isinstance(claims.get("email"), str)
        or claims.get("email_verified") is not True
    ):
        raise GoogleOAuthError("Google account verification failed.")
    return claims
