#!/usr/bin/env python3
"""
dictacode bootstrap (phase 1)
- Run as root (or via sudo).
- Idempotent-ish: safe to re-run.
- Supports:
  * --target {pi5,pi0}
  * -U / --upgrade  (apt-get dist-upgrade before everything else)

For now, pi5 and pi0 share the same base package list and user setup.
Later, target-specific bits can diverge in run_bootstrap().
"""

import argparse
import os
import pwd
import subprocess
import sys
from typing import List

PI5_APT_PACKAGES = [
    "git",
    "openssh-client",
    "curl",
    "build-essential",
    "cmake",
    "pkg-config",
    "python3",
    "python3-venv",
    "python3-dev",
    "alsa-utils",
    "sox",
    "neovim",
    "tmux",
    "htop",
    "unzip",
]

PI0_APT_PACKAGES = [
    "git",
    "openssh-client",
    "curl",
    "python3",
    "python3-venv",
    "unzip",
]

DEV_USER = "dictacode"
DEV_GROUPS = ["audio", "video", "plugdev", "dialout"]


# ----- helpers --------------------------------------------------------------


def run(cmd: List[str]) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_root() -> None:
    if os.geteuid() != 0:
        print("ERROR: run as root or via sudo", file=sys.stderr)
        sys.exit(1)


def apt_update() -> None:
    run(["apt-get", "update"])


def apt_full_upgrade() -> None:
    run(["apt-get", "dist-upgrade", "-y"])


def apt_install(packages: List[str]) -> None:
    run(["apt-get", "install", "-y", *packages])


def user_exists(name: str) -> bool:
    try:
        pwd.getpwnam(name)
        return True
    except KeyError:
        return False


def ensure_user(name: str) -> None:
    if user_exists(name):
        print(f"user '{name}' already exists, skipping creation")
        return
    print(f"creating user '{name}'")
    run(["useradd", "-m", "-s", "/bin/bash", name])
    print(f"NOTE: set a password later with: passwd {name}")


def ensure_groups(name: str, groups: List[str]) -> None:
    group_list = ",".join(groups)
    print(f"ensuring user '{name}' is in groups: {group_list}")
    run(["usermod", "-aG", group_list, name])


# ----- core callable --------------------------------------------------------


def run_bootstrap(target: str, upgrade: bool) -> None:
    """
    Core logic, callable from tests or other code.

    For now:
      - pi5 and pi0 use the same package set and user.
      - target is mainly for future branching and for logging.
    """
    ensure_root()
    print("=== dictacode bootstrap: phase 1 (apt + user) ===")
    print(f"Target: {target}")

    apt_update()

    if upgrade:
        print(">>> performing full system upgrade (dist-upgrade)")
        apt_full_upgrade()

    if target == "pi5":
        pkgs = PI5_APT_PACKAGES
    elif target == "pi0":
        pkgs = PI0_APT_PACKAGES
    else:
        print(f"Unknown target: {target}", file=sys.stderr)
        sys.exit(1)

    apt_install(pkgs)
    ensure_user(DEV_USER)
    ensure_groups(DEV_USER, DEV_GROUPS)

    print("=== done ===")
    print(f"Next: su - {DEV_USER}")


# ----- argparse / entrypoint -----------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bootstrap_pi5_phase1",
        description="dictacode bootstrap (phase 1, apt + user)",
    )
    parser.add_argument(
        "--target",
        choices=["pi5", "pi0"],
        required=True,
        help="device target type",
    )
    parser.add_argument(
        "-U",
        "--upgrade",
        action="store_true",
        help="fully upgrade the system (dist-upgrade) prior to bootstrap",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_bootstrap(target=args.target, upgrade=args.upgrade)


if __name__ == "__main__":
    main()
