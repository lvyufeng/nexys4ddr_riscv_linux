#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ -f /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh ]; then
  set +u
  # shellcheck disable=SC1091
  source /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh
  set -u
fi

if ! command -v vivado >/dev/null 2>&1; then
  echo "Missing vivado in PATH. Source Vivado settings64.sh first." >&2
  exit 1
fi

vivado -mode batch -source scripts/program_litex_nexys4ddr.tcl
