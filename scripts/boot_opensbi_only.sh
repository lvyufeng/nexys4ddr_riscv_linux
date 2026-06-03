#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

PORT=${1:-/dev/ttyUSB1}
if [ $# -gt 0 ]; then
  shift
fi

if [ ! -d .venv ]; then
  echo "Missing .venv. Run scripts/bootstrap_litex.sh first." >&2
  exit 1
fi
PYTHON=${PYTHON:-.venv/bin/python}
if [ ! -x "$PYTHON" ]; then
  PYTHON=python3
fi
if [ ! -f linux/images/opensbi.bin ]; then
  echo "Missing linux/images/opensbi.bin. Run scripts/build_opensbi_litex.sh first." >&2
  exit 1
fi
if [ ! -f linux/images/rv32.dtb ]; then
  echo "Missing linux/images/rv32.dtb. Run scripts/build_litex_dtb.sh first." >&2
  exit 1
fi

TMP_DIR=$(mktemp -d)
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT
TMP_JSON="$TMP_DIR/opensbi_only_images.json"
python3 - "$TMP_JSON" <<'PYJSON'
from pathlib import Path
import json, sys
Path(sys.argv[1]).write_text(json.dumps({
    "rv32.dtb": "0x40ef0000",
    "opensbi.bin": "0x40f00000",
}, indent=2))
PYJSON
cp linux/images/rv32.dtb "$TMP_DIR/rv32.dtb"
cp linux/images/opensbi.bin "$TMP_DIR/opensbi.bin"

# Use the same non-interactive SFL uploader as the full Linux path. It can issue
# `serialboot` from an already-idle LiteX BIOS prompt and does not require stdin
# to be a real TTY.
"$PYTHON" scripts/serial_boot_litex_images.py \
  --port "$PORT" \
  --speed "${LITEX_BAUD:-1000000}" \
  --images "$TMP_JSON" \
  --chunk-size "${LITEX_SFL_CHUNK:-251}" \
  --ack-window "${LITEX_SFL_ACK_WINDOW:-64}" \
  --loader-timeout "${LITEX_LOADER_TIMEOUT:-30}" \
  --console-timeout "${LITEX_CONSOLE_TIMEOUT:-180}" \
  --exit-on "OpenSBI" \
  --log "${LITEX_BOOT_TRANSCRIPT:-/tmp/boot_opensbi_only.log}" \
  "$@"
