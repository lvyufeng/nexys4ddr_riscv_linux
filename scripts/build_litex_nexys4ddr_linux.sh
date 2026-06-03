#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "Missing .venv. Run scripts/bootstrap_litex.sh first." >&2
  exit 1
fi

if [ -f /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh ]; then
  # Avoid nounset issues from vendor scripts under `set -u`.
  set +u
  # shellcheck disable=SC1091
  source /mnt/data1/Xilinx/2025.2/Vivado/settings64.sh
  set -u
fi

XILINX_RISCV=/mnt/data1/Xilinx/2025.2/gnu/riscv/lin/bin
if [ -d "$XILINX_RISCV" ]; then
  export PATH="$XILINX_RISCV:$PATH"
fi

if ! command -v riscv64-unknown-elf-gcc >/dev/null 2>&1; then
  echo "Missing riscv64-unknown-elf-gcc in PATH." >&2
  echo "Vivado 2025.2 usually provides it under: $XILINX_RISCV" >&2
  exit 1
fi

if ! command -v vivado >/dev/null 2>&1; then
  echo "Missing vivado in PATH. Source Vivado settings64.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

OUT_DIR=${1:-build/litex_nexys4ddr_linux}
UART_BAUDRATE=${LITEX_UART_BAUDRATE:-1000000}
mkdir -p "$(dirname "$OUT_DIR")"

python3 -m litex_boards.targets.digilent_nexys4ddr \
  --cpu-type=vexriscv_smp \
  --cpu-variant=linux \
  --cpu-count="${CPU_COUNT:-1}" \
  --hardware-breakpoints=0 \
  --uart-baudrate="$UART_BAUDRATE" \
  --build \
  --output-dir "$OUT_DIR" \
  --soc-json "$OUT_DIR/csr.json" \
  --soc-csv "$OUT_DIR/csr.csv" \
  --memory-x "$OUT_DIR/memory.x"

python3 third_party/litex/litex/tools/litex_json2dts_linux.py \
  "$OUT_DIR/csr.json" \
  --root-device "${ROOT_DEVICE:-ram0}" \
  > "$OUT_DIR/digilent_nexys4ddr_linux.dts"

printf '\nLiteX Nexys4 DDR Linux-capable build complete. Output directory: %s\n' "$OUT_DIR"
printf 'LiteX UART baudrate: %s\n' "$UART_BAUDRATE"
find "$OUT_DIR" -maxdepth 4 -type f \( -name '*.bit' -o -name '*.bin' -o -name 'bios.*' -o -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' -o -name '*timing*.rpt' \) | sort
