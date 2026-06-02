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

OUT_DIR=${1:-build/litex_nexys4ddr}
mkdir -p "$(dirname "$OUT_DIR")"

python3 -m litex_boards.targets.digilent_nexys4ddr \
  --build \
  --output-dir "$OUT_DIR" \
  --soc-json "$OUT_DIR/csr.json" \
  --soc-csv "$OUT_DIR/csr.csv" \
  --memory-x "$OUT_DIR/memory.x"

printf '\nLiteX Nexys4 DDR build complete. Output directory: %s\n' "$OUT_DIR"
find "$OUT_DIR" -maxdepth 3 -type f \( -name '*.bit' -o -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*timing*summary*.rpt' \) | sort
