"""Tests for the badge-only license system (v0.3.3).

These tests verify that the license validation:
- Returns 'free' tier when no token present
- Validates Ed25519 signatures correctly
- Falls back gracefully on any error
- Never blocks features (purely cosmetic)
"""

import base64
import json

import pytest


class TestBadgeState:
    """Tests for BadgeState dataclass."""

    def test_default_badge_state(self):
        """Default BadgeState should be free tier."""
        from dictacode_stt.license import BadgeState

        state = BadgeState()
        assert state.tier == "free"
        assert state.badge is None
        assert state.name is None
        assert state.issued_at is None

    def test_badge_state_to_dict(self):
        """BadgeState.to_dict() should return correct structure."""
        from dictacode_stt.license import BadgeState

        state = BadgeState(
            tier="donor",
            badge="Test User",
            name="Test User",
            issued_at="2025-12-01",
        )
        result = state.to_dict()

        assert result == {
            "tier": "donor",
            "badge": "Test User",
            "name": "Test User",
            "issued_at": "2025-12-01",
        }


class TestLoadBadgeState:
    """Tests for load_badge_state() function."""

    def test_free_when_no_token(self):
        """Should return free tier when no token provided."""
        from dictacode_stt.license import load_badge_state

        state = load_badge_state(token=None)
        assert state.tier == "free"
        assert state.badge is None

    def test_free_when_empty_token(self):
        """Should return free tier for empty token."""
        from dictacode_stt.license import load_badge_state

        state = load_badge_state(token="")
        assert state.tier == "free"

    def test_malformed_token_no_separator(self):
        """Malformed token without dot should return free tier."""
        from dictacode_stt.license import load_badge_state

        state = load_badge_state(token="no-dot-here")
        assert state.tier == "free"

    def test_unknown_kid_fallback(self):
        """Unknown key id should fall back to free tier."""
        from dictacode_stt.license import load_badge_state

        # Create token with unknown kid
        payload = json.dumps({"kid": "unknown-key-999", "tier": "donor"})
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        token = f"{payload_b64}.fake_signature"

        state = load_badge_state(token=token)
        assert state.tier == "free"

    def test_invalid_signature_fallback(self):
        """Invalid signature should fall back to free tier."""
        from dictacode_stt.license import PUBLIC_KEYS, load_badge_state

        # Use a real kid but with invalid signature
        kid = list(PUBLIC_KEYS.keys())[0]
        payload = json.dumps({"kid": kid, "tier": "donor", "name": "Test"})
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        # Invalid signature (random bytes)
        sig_b64 = base64.urlsafe_b64encode(b"invalid_sig").decode().rstrip("=")
        token = f"{payload_b64}.{sig_b64}"

        state = load_badge_state(token=token)
        assert state.tier == "free"

    def test_invalid_json_fallback(self):
        """Invalid JSON in payload should fall back to free tier."""
        from dictacode_stt.license import load_badge_state

        # Base64 encoded invalid JSON
        payload_b64 = base64.urlsafe_b64encode(b"not json").decode().rstrip("=")
        token = f"{payload_b64}.fake_sig"

        state = load_badge_state(token=token)
        assert state.tier == "free"


class TestTierValidation:
    """Tests for tier validation."""

    def test_valid_tiers_constant(self):
        """VALID_TIERS should contain all expected tiers."""
        from dictacode_stt.license import VALID_TIERS

        expected = ("free", "supporter", "donor", "contributor", "multiplicator")
        assert VALID_TIERS == expected

    def test_public_keys_exist(self):
        """PUBLIC_KEYS should contain at least one key."""
        from dictacode_stt.license import PUBLIC_KEYS

        assert len(PUBLIC_KEYS) > 0
        assert "2025-01" in PUBLIC_KEYS


class TestValidToken:
    """Tests with valid token using test keypair."""

    @pytest.fixture
    def test_keypair(self):
        """Generate a test Ed25519 keypair."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

        return private_key, pub_pem

    @pytest.fixture
    def valid_token(self, test_keypair):
        """Generate a valid signed token."""
        private_key, pub_pem = test_keypair

        payload = json.dumps({
            "kid": "test-key",
            "tier": "donor",
            "name": "Test User",
            "issued_at": "2025-12-01",
        }).encode()

        sig = private_key.sign(payload)

        # Base64url encode without padding
        payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")

        return f"{payload_b64}.{sig_b64}", pub_pem

    def test_valid_token_returns_badge(self, valid_token, monkeypatch):
        """Valid token should return correct badge state."""
        token, pub_pem = valid_token

        from dictacode_stt import license

        monkeypatch.setattr(license, "PUBLIC_KEYS", {"test-key": pub_pem})

        state = license.load_badge_state(token=token)
        assert state.tier == "donor"
        assert state.badge == "Test User"
        assert state.name == "Test User"
        assert state.issued_at == "2025-12-01"

    @pytest.mark.parametrize("tier", ["supporter", "donor", "contributor", "multiplicator"])
    def test_valid_tiers_accepted(self, tier, test_keypair, monkeypatch):
        """All valid tiers should be accepted as-is."""
        private_key, pub_pem = test_keypair

        payload = json.dumps({
            "kid": "test-key",
            "tier": tier,
            "name": "Test",
        }).encode()

        sig = private_key.sign(payload)
        payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
        token = f"{payload_b64}.{sig_b64}"

        from dictacode_stt import license

        monkeypatch.setattr(license, "PUBLIC_KEYS", {"test-key": pub_pem})

        state = license.load_badge_state(token=token)
        assert state.tier == tier

    def test_unknown_tier_falls_back_to_free(self, test_keypair, monkeypatch):
        """Unknown tier in valid token should fall back to free."""
        private_key, pub_pem = test_keypair

        payload = json.dumps({
            "kid": "test-key",
            "tier": "invalid_tier_name",
            "name": "Test",
        }).encode()

        sig = private_key.sign(payload)
        payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
        token = f"{payload_b64}.{sig_b64}"

        from dictacode_stt import license

        monkeypatch.setattr(license, "PUBLIC_KEYS", {"test-key": pub_pem})

        state = license.load_badge_state(token=token)
        assert state.tier == "free"  # Falls back due to invalid tier


class TestKeyRotation:
    """Tests for key rotation support."""

    def test_multiple_keys_supported(self, monkeypatch):
        """Multiple keys should be supported for rotation."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        # Generate two keypairs
        priv1 = Ed25519PrivateKey.generate()
        pub1_pem = priv1.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

        priv2 = Ed25519PrivateKey.generate()
        pub2_pem = priv2.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

        from dictacode_stt import license

        monkeypatch.setattr(license, "PUBLIC_KEYS", {
            "key-old": pub1_pem,
            "key-new": pub2_pem,
        })

        # Token signed with old key
        payload1 = json.dumps({"kid": "key-old", "tier": "donor", "name": "Old"}).encode()
        sig1 = priv1.sign(payload1)
        token1 = base64.urlsafe_b64encode(payload1).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig1).decode().rstrip("=")

        # Token signed with new key
        payload2 = json.dumps({"kid": "key-new", "tier": "contributor", "name": "New"}).encode()
        sig2 = priv2.sign(payload2)
        token2 = base64.urlsafe_b64encode(payload2).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig2).decode().rstrip("=")

        # Both should validate
        state1 = license.load_badge_state(token=token1)
        assert state1.tier == "donor"
        assert state1.name == "Old"

        state2 = license.load_badge_state(token=token2)
        assert state2.tier == "contributor"
        assert state2.name == "New"
