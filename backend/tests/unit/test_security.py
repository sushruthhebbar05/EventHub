from datetime import timedelta

import pytest
from jose import jwt

from app.config import settings
from app.utils.security import create_access_token, decode_access_token, hash_password, verify_password
from app.utils.timeutil import utcnow

pytestmark = pytest.mark.unit


def test_password_is_hashed_and_verifiable():
    h = hash_password("Secret123")
    assert h != "Secret123" and h.startswith("$2")
    assert verify_password("Secret123", h)
    assert not verify_password("secret123", h)


def test_same_password_gets_different_salts():
    assert hash_password("Secret123") != hash_password("Secret123")


def test_verify_password_handles_garbage_hash():
    assert verify_password("x", "not-a-hash") is False


def test_jwt_roundtrip():
    assert decode_access_token(create_access_token(42)) == 42


def test_jwt_rejects_garbage_tampered_and_wrong_secret():
    assert decode_access_token("garbage") is None
    token = create_access_token(1)
    assert decode_access_token(token[:-3] + "abc") is None
    forged = jwt.encode({"sub": "1", "exp": utcnow() + timedelta(hours=1)}, "some-other-secret", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_jwt_rejects_expired_token():
    expired = jwt.encode({"sub": "1", "exp": utcnow() - timedelta(seconds=5)}, settings.jwt_secret, algorithm="HS256")
    assert decode_access_token(expired) is None
