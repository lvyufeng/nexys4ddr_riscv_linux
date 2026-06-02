#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ ! -d .venv ]; then
  echo "Missing .venv. Run scripts/bootstrap_litex.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

OUT_DIR=${1:-build/litex_nexys4ddr_probe}
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

python3 -m litex_boards.targets.digilent_nexys4ddr \
  --build \
  --no-compile \
  --output-dir "$OUT_DIR" \
  --soc-json "$OUT_DIR/csr.json" \
  --soc-csv "$OUT_DIR/csr.csv" \
  --memory-x "$OUT_DIR/memory.x"

printf '\nGenerated LiteX Nexys4 DDR probe files in %s\n' "$OUT_DIR"
find "$OUT_DIR" -maxdepth 2 -type f | sort
