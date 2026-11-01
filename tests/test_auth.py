import base64
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jwt
import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from custom_components.ha_agent.auth import CertificateIdentity,AuthenticationError
TENANT="00000000-0000-0000-0000-000000000001"
CLIENT="00000000-0000-0000-0000-000000000002"
def identity(tmp_path,expired=False):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"HA test")])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=2)).not_valid_after(now+timedelta(days=-1 if expired else 1)).sign(key,hashes.SHA256())
    key_path=tmp_path/"test.key"; cert_path=tmp_path/"test.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return CertificateIdentity.load(TENANT,CLIENT,key_path,cert_path),key,cert
def test_certificate_assertion_uses_microsoft_ps256_and_correct_audience(tmp_path):
    value,key,cert=identity(tmp_path)
    assertion=value.assertion()
    claims=jwt.decode(assertion,key.public_key(),algorithms=["PS256"],audience=value.token_url)
    assert claims["iss"]==CLIENT and claims["sub"]==CLIENT and claims["exp"]-claims["iat"]==300
    header=jwt.get_unverified_header(assertion)
    assert header["x5t#S256"]==base64.urlsafe_b64encode(cert.fingerprint(hashes.SHA256())).decode().rstrip("=")
    assert "PRIVATE" not in assertion
def test_expired_certificate_is_rejected(tmp_path):
    value,_,_=identity(tmp_path,True)
    with pytest.raises(AuthenticationError):value.assertion()
def test_identity_representation_contains_no_key_material(tmp_path):
    value,_,_=identity(tmp_path)
    assert "PRIVATE" not in repr(value) and "private_key" not in repr(value)
