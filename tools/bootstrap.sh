#!/usr/bin/env sh
# dictacode bootstrap orchestrator
# - POSIX sh
# - Options:
#     -U        fully upgrade system before bootstrap
#     -h        show help
#     -t <pi5|pi0>  target device type

set -eu

REPO_OWNER="cprima-homelab"
REPO_NAME="dictacode"
# Note: this must match how you call raw.githubusercontent.com
BRANCH_PATH="${DICTACODE_BRANCH:-refs/heads/exploration}"

RAW_BASE="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH_PATH}"
PY_BOOTSTRAP_PATH="tools/bootstrap_pi5_phase1.py"

UPGRADE=0
TARGET=""
TMP_PY=""

__usage() {
    cat <<'EOF'
Usage: bootstrap.sh [OPTIONS]

Options:
  -U              Fully upgrade the system (apt-get dist-upgrade) prior to bootstrap
  -t <pi5|pi0>    Target device type (required)
  -h              Show this help and exit

Examples:
  # Pi5, no dist-upgrade
  curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/refs/heads/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi5

  # Pi5, with dist-upgrade
  curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/refs/heads/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi5 -U

  # Pi0, no dist-upgrade
  curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/refs/heads/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi0
EOF
}

cleanup() {
    if [ -n "$TMP_PY" ] && [ -f "$TMP_PY" ]; then
        rm -f "$TMP_PY"
    fi
}
trap cleanup EXIT INT TERM

# ensure python3 exists
ensure_python3() {
    if command -v python3 >/dev/null 2>&1; then
        return
    fi
    echo "python3 not found, installing via apt-get..." >&2
    apt-get update
    apt-get install -y python3
}

# parse options (salt-style)
while getopts "Uht:" opt; do
    case "$opt" in
        U)
            UPGRADE=1
            ;;
        t)
            TARGET="$OPTARG"
            ;;
        h)
            __usage
            exit 0
            ;;
        *)
            __usage
            exit 1
            ;;
    esac
done
shift $((OPTIND - 1))

if [ -z "$TARGET" ]; then
    echo "ERROR: -t <pi5|pi0> is required" >&2
    __usage
    exit 1
fi

case "$TARGET" in
    pi5|pi0)
        ;;
    *)
        echo "ERROR: invalid target '$TARGET' (must be pi5 or pi0)" >&2
        __usage
        exit 1
        ;;
esac

echo "dictacode: bootstrap (phase 1, apt)"
echo "Branch path: ${BRANCH_PATH}"
echo "Target: ${TARGET}"
echo "Upgrade before bootstrap: ${UPGRADE}"

TMP_PY="$(mktemp /tmp/dictacode_bootstrap_pi5_phase1.XXXXXX.py)"

echo "Fetching ${PY_BOOTSTRAP_PATH} from ${RAW_BASE} ..."
if ! curl -fsSL "${RAW_BASE}/${PY_BOOTSTRAP_PATH}" -o "${TMP_PY}"; then
    echo "ERROR: failed to fetch ${RAW_BASE}/${PY_BOOTSTRAP_PATH}" >&2
    exit 1
fi

# simple 404 guard
if grep -q "404: Not Found" "$TMP_PY"; then
    echo "ERROR: GitHub returned 404 for ${RAW_BASE}/${PY_BOOTSTRAP_PATH}" >&2
    exit 1
fi

PY_ARGS="--target ${TARGET}"
if [ "$UPGRADE" -eq 1 ]; then
    PY_ARGS="$PY_ARGS --upgrade"
fi

ensure_python3
echo "Running: python3 ${TMP_PY} ${PY_ARGS}"
python3 "${TMP_PY}" ${PY_ARGS}

echo "dictacode: bootstrap done."
