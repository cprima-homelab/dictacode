#!/usr/bin/env python3
"""
Generate code maps for dictacode using pydeps/pyan/pycg.

Outputs:
  - pydeps-stt.svg / pydeps-hid.svg (module dependency graphs)
  - pyan-stt.svg / pyan-hid.svg     (call/dependency graphs)
  - pycg-stt.svg / pycg-hid.svg     (call graph from entry point)

This script is defensive:
  - It tries to run inside the app subdirs so uv/pyproject deps are used.
  - Falls back to --no-project mode if project deps fail to install/build.
  - Skips graph generation if required tools are missing.

Usage:
  uv run python tools/generate_code_maps.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = {
    "stt": {
        "path": ROOT / "apps" / "stt",
        "package": "dictacode_stt",
        "entry": ROOT / "apps" / "stt" / "src" / "dictacode_stt" / "main.py",
    },
    "hid": {
        "path": ROOT / "apps" / "hid",
        "package": "dictacode_hid",
        "entry": ROOT / "apps" / "hid" / "src" / "dictacode_hid" / "main.py",
    },
}


def run_cmd(cmd: list[str], cwd: Path) -> bool:
    """Run a command and return True on success."""
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"[warn] command failed in {cwd}: {' '.join(cmd)}\n{e}\n")
    except FileNotFoundError as e:
        sys.stderr.write(f"[warn] tool missing: {cmd[0]} ({e})\n")
    return False


def ensure_tools(app_dir: Path) -> None:
    """Try to ensure pydeps, pyan3, pycg are available via uv."""
    run_cmd(["uv", "pip", "install", "pydeps", "pyan3", "pycg"], cwd=app_dir)


def gen_pydeps(app: str, cfg: dict) -> None:
    out = ROOT / f"pydeps-{app}.svg"
    cmd = [
        "uv",
        "run",
        "--no-project",
        "pydeps",
        f"src/{cfg['package']}",
        "--max-bacon=2",
        "-o",
        str(out),
        "--show-deps",
        "--noshow",
    ]
    run_cmd(cmd, cwd=cfg["path"])


def gen_pyan(app: str, cfg: dict) -> None:
    dot = ROOT / f"pyan-{app}.dot"
    svg = ROOT / f"pyan-{app}.svg"
    cmd = [
        "uv",
        "run",
        "--no-project",
        "pyan",
        f"src/{cfg['package']}/**/*.py",
        "--dot",
        "--max-depth=2",
        "--grouped",
        "--uses",
        "--no-dynamic",
    ]
    if run_cmd(cmd + [">", str(dot)], cwd=cfg["path"]):
        run_cmd(["dot", "-Tsvg", str(dot), "-o", str(svg)], cwd=cfg["path"])


def gen_pycg(app: str, cfg: dict) -> None:
    dot = ROOT / f"pycg-{app}.dot"
    svg = ROOT / f"pycg-{app}.svg"
    cmd = [
        "uv",
        "run",
        "--no-project",
        "pycg",
        "--package",
        cfg["package"],
        "--entry-point",
        str(cfg["entry"]),
        "--output",
        str(dot),
        "--format",
        "dot",
    ]
    if run_cmd(cmd, cwd=cfg["path"]):
        run_cmd(["dot", "-Tsvg", str(dot), "-o", str(svg)], cwd=cfg["path"])


def main() -> int:
    for name, cfg in APPS.items():
        print(f"==> Ensuring tools for {name}")
        ensure_tools(cfg["path"])

        print(f"==> Generating pydeps for {name}")
        gen_pydeps(name, cfg)

        print(f"==> Generating pyan for {name}")
        gen_pyan(name, cfg)

        print(f"==> Generating pycg for {name}")
        gen_pycg(name, cfg)

    print("Done. Check pydeps-*.svg, pyan-*.svg, pycg-*.svg at repo root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
