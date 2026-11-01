"""OAuth certificate identity. Private keys never leave the local host."""
import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path
import time
from uuid import UUID, uuid4

import aiohttp
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

class AuthenticationError(Exception):
    """A sanitized authentication failure."""

@dataclass(repr=False)
class CertificateIdentity:
    tenant_id: str
    client_id: str
    private_key: object
    thumbprint: str
    expires_at: float

    @classmethod
    def load(cls, tenant_id, client_id, key_path, cert_path):
        tenant_id, client_id = str(UUID(tenant_id)), str(UUID(client_id))
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
        public = lambda value: value.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if public(key.public_key()) != public(cert.public_key()):
            raise AuthenticationError("Certificate does not match the private key")
        return cls(tenant_id, client_id, key,
                   base64.urlsafe_b64encode(cert.fingerprint(hashes.SHA256())).decode().rstrip("="),
                   cert.not_valid_after_utc.timestamp())

    @property
    def token_url(self):
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def assertion(self):
        now = int(time.time())
        if self.expires_at <= now:
            raise AuthenticationError("The HA-Agent certificate has expired")
        return jwt.encode(
            {"aud": self.token_url, "iss": self.client_id, "sub": self.client_id,
             "jti": str(uuid4()), "iat": now, "nbf": now - 30, "exp": now + 300},
            self.private_key, algorithm="PS256", headers={"x5t#S256": self.thumbprint},
        )

class TokenProvider:
    def __init__(self, session, identity):
        self.session, self.identity = session, identity
        self._token = None
        self._expires = 0
        self._lock = asyncio.Lock()

    async def token(self):
        async with self._lock:
            if self._token and self._expires > time.time() + 120:
                return self._token
            assertion = self.identity.assertion()
            async with self.session.post(
                self.identity.token_url,
                data={"client_id": self.identity.client_id, "scope": "https://ai.azure.com/.default",
                      "grant_type": "client_credentials",
                      "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                      "client_assertion": assertion},
                timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise AuthenticationError(f"Microsoft OAuth rejected the connection (HTTP {response.status})")
                data = await response.json()
            if not isinstance(data.get("access_token"), str) or float(data.get("expires_in", 0)) <= 120:
                raise AuthenticationError("Microsoft OAuth returned an invalid token response")
            self._token = data["access_token"]
            self._expires = time.time() + float(data["expires_in"])
            return self._token
