#!/usr/bin/env python3
"""
generate_license_key.py - Helper to (re)generate Ed25519 key pairs from a seed.

Usage:
    ./generate_license_key.py --seed "cat" --kid key-1 --outdir /tmp/keys

Outputs:
    - <outdir>/<kid>-priv.pem
    - <outdir>/<kid>-pub.pem

The seed is hashed via SHA-256 to derive a stable 32-byte private key, so running
with the same seed/kid regenerates the same key pair. Use different seeds for
different key IDs.
"""

import argparse
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def derive_ed25519_from_seed_string(seed_str: str) -> ed25519.Ed25519PrivateKey:
    """Derive a deterministic Ed25519 private key from a UTF-8 seed string."""
    seed_bytes = seed_str.encode("utf-8")
    key_bytes = hashlib.sha256(seed_bytes).digest()  # Always 32 bytes
    return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)


def write_keypair(seed: str, kid: str, outdir: Path) -> None:
    """Derive and write a PEM keypair to outdir using kid as filename prefix."""
    outdir.mkdir(parents=True, exist_ok=True)

    priv = derive_ed25519_from_seed_string(seed)
    pub = priv.public_key()

    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = outdir / f"{kid}-priv.pem"
    pub_path = outdir / f"{kid}-pub.pem"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)

    print(f"Wrote private key: {priv_path}")
    print(f"Wrote public  key: {pub_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Ed25519 keypair from seed string."
    )
    parser.add_argument(
        "--seed",
        required=True,
        help="Seed string (UTF-8). Use a strong, unique value per key.",
    )
    parser.add_argument(
        "--kid",
        default="key-1",
        help="Key ID used for output filenames (default: key-1).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("dist/keys"),
        help="Output directory (default: dist/keys).",
    )
    args = parser.parse_args()

    write_keypair(seed=args.seed, kid=args.kid, outdir=args.outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
