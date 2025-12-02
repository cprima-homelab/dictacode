"""Badge-only license key validation (cosmetic, never blocks features).

This module implements a recognition system for dictacode contributors,
donors, and supporters. The license is purely cosmetic and NEVER gates
any features.

Token format: <base64url(payload_json)>.<base64url(signature)>

Payload example:
{
    "kid": "2025-01",
    "tier": "donor",
    "name": "Lorem Ipsum Dev",
    "issued_at": "2025-12-01"
}
"""

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
class BadgeState:
    """Badge state returned by license validation."""

    tier: str = "free"
    badge: Optional[str] = None
    name: Optional[str] = None
    issued_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier": self.tier,
            "badge": self.badge,
            "name": self.name,
            "issued_at": self.issued_at,
        }


def load_badge_state(token: Optional[str] = None) -> BadgeState:
    """
    Load and validate license token, returning badge state.

    Falls back to 'free' tier on any error (never blocks).

    Args:
        token: Optional token string. If None, searches LICENSE_PATHS.

    Returns:
        BadgeState with tier, badge, name, and issued_at fields.
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
        return BadgeState()  # free tier

    # 2. Parse token
    try:
        if "." not in token:
            logger.warning("Malformed license token (no separator)")
            return BadgeState()

        payload_b64, sig_b64 = token.split(".", 1)

        # Add padding for base64url decoding
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + "==")

        data = json.loads(payload_bytes)
        kid = data.get("kid")

        if not kid or kid not in PUBLIC_KEYS:
            logger.warning("Unknown license key id (kid=%s)", kid)
            return BadgeState()

        # 3. Verify signature (lazy import to avoid startup cost if no license)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        pub_pem = PUBLIC_KEYS[kid]
        pub_key = load_pem_public_key(pub_pem)

        if not isinstance(pub_key, Ed25519PublicKey):
            logger.warning("Key %s is not Ed25519", kid)
            return BadgeState()

        pub_key.verify(sig_bytes, payload_bytes)

        # 4. Valid! Validate tier and return badge state
        tier = data.get("tier", "free")
        if tier not in VALID_TIERS:
            logger.warning("Unknown tier '%s', falling back to free", tier)
            tier = "free"

        return BadgeState(
            tier=tier,
            badge=data.get("name"),
            name=data.get("name"),
            issued_at=data.get("issued_at"),
        )

    except Exception as e:
        logger.warning("License validation failed: %s", e)
        return BadgeState()
