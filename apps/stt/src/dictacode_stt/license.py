"""Badge-only license key validation (cosmetic, never blocks features).

This module implements a recognition system for dictacode contributors,
donors, and supporters. The license is purely cosmetic and NEVER gates
any features.

Token format: <base64url(payload_json)>.<base64url(signature)>

Payload examples:

Legacy single-badge (v0.3.3):
{
    "kid": "2025-01",
    "tier": "donor",
    "name": "Lorem Ipsum Dev",
    "issued_at": "2025-12-01"
}

Multi-badge (v0.3.11):
{
    "kid": "2025-01",
    "badges": [
        {"tier": "donor", "name": "Lorem Ipsum", "issued_at": "2025-12-01"},
        {"tier": "contributor", "name": "Code Contribution", "issued_at": "2025-11-15"}
    ]
}
"""

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("dictacode.stt.license")

# Valid badge tiers (ordered by recognition level)
VALID_TIERS = ("free", "supporter", "donor", "contributor", "multiplicator")

# Ed25519 public keys for signature verification
# kid → PEM-encoded public key
PUBLIC_KEYS = {
    "2025-01": b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAFuGy0GCjVpuUc9AXJC8SxhtSRevbh/dKm8qenw/j4LQ=
-----END PUBLIC KEY-----""",
}

# License file search paths (user scope first, then system)
LICENSE_PATHS = [
    Path.home() / ".config/dictacode/license.key",
    Path("/etc/dictacode/license.key"),
]


@dataclass
class Badge:
    """Single badge from a license token (v0.3.11)."""

    kid: str
    tier: str
    name: Optional[str] = None
    issued_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "kid": self.kid,
            "tier": self.tier,
            "name": self.name,
            "issued_at": self.issued_at,
        }


@dataclass
class BadgeState:
    """Badge state with multiple badges support (v0.3.11).

    Maintains backward compatibility with v0.3.3 single-badge API.
    """

    badges: List[Badge] = field(default_factory=list)
    token_present: bool = False

    @property
    def primary(self) -> Optional[Badge]:
        """First badge or None if empty."""
        return self.badges[0] if self.badges else None

    @property
    def tier(self) -> str:
        """Primary tier (backward compat with v0.3.3)."""
        return self.primary.tier if self.primary else "free"

    @property
    def badge(self) -> Optional[str]:
        """Primary badge name (backward compat with v0.3.3)."""
        return self.primary.name if self.primary else None

    @property
    def name(self) -> Optional[str]:
        """Primary name (backward compat with v0.3.3)."""
        return self.primary.name if self.primary else None

    @property
    def issued_at(self) -> Optional[str]:
        """Primary issued_at (backward compat with v0.3.3)."""
        return self.primary.issued_at if self.primary else None

    @property
    def tiers(self) -> List[str]:
        """All tier names."""
        return [b.tier for b in self.badges]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Includes both v0.3.11 multi-badge fields and v0.3.3 backward compat fields.
        """
        primary = self.primary
        return {
            # v0.3.11 fields
            "badges": [b.to_dict() for b in self.badges],
            "tiers": self.tiers,
            "primary": primary.to_dict() if primary else None,
            "token_present": self.token_present,
            # v0.3.3 backward compat fields
            "tier": self.tier,
            "badge": self.badge,
            "name": self.name,
            "issued_at": self.issued_at,
        }


def _verify_signature(kid: Optional[str], sig_bytes: bytes, payload_bytes: bytes) -> bool:
    """Verify Ed25519 signature over payload.

    Args:
        kid: Key ID to look up public key
        sig_bytes: Signature bytes
        payload_bytes: Raw payload bytes that were signed

    Returns:
        True if signature is valid, False otherwise
    """
    if not kid or kid not in PUBLIC_KEYS:
        logger.warning("Unknown license key id (kid=%s)", kid)
        return False

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        pub_pem = PUBLIC_KEYS[kid]
        pub_key = load_pem_public_key(pub_pem)

        if not isinstance(pub_key, Ed25519PublicKey):
            logger.warning("Key %s is not Ed25519", kid)
            return False

        pub_key.verify(sig_bytes, payload_bytes)
        return True

    except Exception as e:
        logger.warning("Signature verification failed: %s", e)
        return False


def load_badge_state(token: Optional[str] = None) -> BadgeState:
    """
    Load and validate license token, returning badge state.

    Supports both legacy single-badge tokens (v0.3.3) and multi-badge tokens (v0.3.11).
    Falls back to 'free' tier on any error (never blocks).

    Args:
        token: Optional token string. If None, searches LICENSE_PATHS.

    Returns:
        BadgeState with badges list and backward-compat fields.
    """
    # 1. Find token from file if not provided
    if token is None:
        for path in LICENSE_PATHS:
            if path.exists():
                try:
                    token = path.read_text().strip()
                    logger.debug("Found license at: %s", path)
                    break
                except Exception as e:
                    logger.warning("Could not read %s: %s", path, e)

    if not token:
        return BadgeState()  # free tier, no token

    # 2. Parse token
    try:
        if "." not in token:
            logger.warning("Malformed license token (no separator)")
            return BadgeState(token_present=True)

        payload_b64, sig_b64 = token.split(".", 1)

        # Add padding for base64url decoding
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + "==")

        data = json.loads(payload_bytes)

        # 3. Get badges array or wrap single badge (backward compat)
        token_kid = data.get("kid")

        if "badges" in data:
            # v0.3.11 multi-badge format
            raw_badges = data["badges"]
        else:
            # v0.3.3 legacy single-badge format - wrap as array
            raw_badges = [data]

        # 4. Verify signature (once for whole token)
        verified = _verify_signature(token_kid, sig_bytes, payload_bytes)

        if not verified:
            logger.warning("Token signature verification failed")
            return BadgeState(token_present=True)  # Invalid but token exists

        # 5. Process badges
        badges = []
        for raw in raw_badges:
            # Per-badge kid overrides token kid
            badge_kid = raw.get("kid", token_kid)
            tier = raw.get("tier", "free")

            if tier not in VALID_TIERS:
                logger.warning("Unknown tier '%s', skipping badge", tier)
                continue

            badges.append(Badge(
                kid=badge_kid or "",
                tier=tier,
                name=raw.get("name"),
                issued_at=raw.get("issued_at"),
            ))

        if not badges:
            logger.info("No valid badges in token")
            return BadgeState(token_present=True)

        logger.info("Loaded %d badge(s): %s", len(badges), [b.tier for b in badges])
        return BadgeState(badges=badges, token_present=True)

    except Exception as e:
        logger.warning("License validation failed: %s", e)
        return BadgeState(token_present=True)
