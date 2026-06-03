#!/usr/bin/env bash
set -euo pipefail

# litex_term needs a real TTY for keyboard/terminal handling. When this script is
# launched from Claude Code or another non-interactive shell, re-run itself under
# `script(1)` to provide a pseudo-terminal.
if [ -z "${LITEX_BOOT_PTY:-}" ] && ! [ -t 0 ] && command -v script >/dev/null 2>&1; then
  transcript=${LITEX_BOOT_TRANSCRIPT:-/tmp/boot_opensbi_only.typescript}
  cmd=$(printf '%q ' "$0" "$@")
  exec env LITEX_BOOT_PTY=1 script -qfec "$cmd" "$transcript"
fi

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

# Start litex_term in serial-boot mode. This listens for the LiteX BIOS
# boot-menu serial prompt and answers it before uploading images. Start this
# shortly after programming/resetting the FPGA so the BIOS boot prompt has not
# timed out yet. If the board is already at the `litex>` prompt, run `reboot`
# manually and immediately re-run this command, or press the FPGA reset button.
timeout --foreground "${LITEX_TERM_TIMEOUT:-180}" \
  .venv/bin/litex_term "$PORT" \
    --speed 115200 \
    --serial-boot \
    --images "$TMP_JSON" \
    --exit-on "OpenSBI" \
    "$@"
