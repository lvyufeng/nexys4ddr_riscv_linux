#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

PORT=${1:-/dev/ttyUSB1}
if [ $# -gt 0 ]; then
  shift
fi

IMAGES=${IMAGES:-linux/images/litex_vexriscv_smp_images.json}
if [ ! -f "$IMAGES" ]; then
  echo "Missing $IMAGES. Run scripts/collect_litex_linux_images.sh first." >&2
  exit 1
fi

PYTHON=${PYTHON:-.venv/bin/python}
if [ ! -x "$PYTHON" ]; then
  PYTHON=python3
fi

# Non-interactive LiteX SFL uploader. Unlike litex_term, this does not require
# stdin to be a real TTY, so it works reliably from SSH/agent/background jobs.
"$PYTHON" scripts/serial_boot_litex_images.py \
  --port "$PORT" \
  --speed "${LITEX_BAUD:-1000000}" \
  --images "$IMAGES" \
  --chunk-size "${LITEX_SFL_CHUNK:-251}" \
  --ack-window "${LITEX_SFL_ACK_WINDOW:-8}" \
  --loader-timeout "${LITEX_LOADER_TIMEOUT:-30}" \
  --console-timeout "${LITEX_CONSOLE_TIMEOUT:-600}" \
  --exit-on "${LITEX_EXIT_ON:-buildroot login:}" \
  --log "${LITEX_BOOT_TRANSCRIPT:-/tmp/boot_litex_linux_serial.log}" \
  "$@"
