#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

DTS=${1:-linux/dts/litex_nexys4ddr_vexriscv_smp.dts}
DTB=${2:-linux/images/rv32.dtb}

DTC=${DTC:-}
if [ -z "$DTC" ]; then
  if command -v dtc >/dev/null 2>&1; then
    DTC=$(command -v dtc)
  elif [ -x /mnt/data1/Xilinx/2025.2/Vivado/bin/dtc ]; then
    DTC=/mnt/data1/Xilinx/2025.2/Vivado/bin/dtc
  else
    echo "Missing dtc. Install device-tree-compiler or source Vivado 2025.2." >&2
    exit 1
  fi
fi

mkdir -p "$(dirname "$DTB")"
"$DTC" -I dts -O dtb -o "$DTB" "$DTS"
printf 'DTB image: %s\n' "$DTB"
ls -l "$DTB"
