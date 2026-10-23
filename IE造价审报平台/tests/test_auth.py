"""
认证模块单元测试
"""
import sys
from pathlib import Path
from datetime import timedelta

import pytest

from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    generate_secret_key,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


class TestPasswordHash:
    def test_hash_and_verify(self):
        plain = "my_secret_password"
        hashed = get_password_hash(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True

    def test_wrong_password(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_unique(self):
        # 同一密码两次哈希结果应不同（盐值）
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_verify_invalid_hash(self):
        # 无效哈希应返回 False 而非抛出
        assert verify_password("any", "not-a-valid-hash") is False


class TestToken:
    def test_create_and_decode(self):
        token = create_access_token({"sub": 1, "username": "admin"})
        assert isinstance(token, str)
        data = decode_token(token)
        assert data is not None
        assert data.user_id == 1
        assert data.username == "admin"

    def test_string_sub(self):
        token = create_access_token({"sub": "42", "username": "user1"})
        data = decode_token(token)
        assert data is not None
        assert data.user_id == 42

    def test_invalid_token_returns_none(self):
        assert decode_token("invalid.token.here") is None
        assert decode_token("") is None

    def test_expired_token(self):
        # 负过期时间 → 立即过期
        token = create_access_token({"sub": 1}, expires_delta=timedelta(seconds=-1))
        data = decode_token(token)
        assert data is None

    def test_custom_expiry(self):
        token = create_access_token(
            {"sub": 5, "username": "tester"},
            expires_delta=timedelta(hours=2),
        )
        data = decode_token(token)
        assert data is not None
        assert data.user_id == 5


class TestSecretKey:
    def test_generate_secret_key(self):
        key = generate_secret_key()
        assert isinstance(key, str)
        assert len(key) > 20

    def test_unique(self):
        k1 = generate_secret_key()
        k2 = generate_secret_key()
        assert k1 != k2
