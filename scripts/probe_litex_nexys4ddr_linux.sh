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

OUT_DIR=${1:-build/litex_nexys4ddr_linux_probe}
EXTRA_LITEX_ARGS=()
if [ "${LITEX_WITH_SPI_SDCARD:-1}" = "1" ] && [ "${LITEX_WITH_SDCARD:-0}" = "1" ]; then
  echo "LITEX_WITH_SPI_SDCARD and LITEX_WITH_SDCARD are mutually exclusive." >&2
  exit 1
fi
if [ "${LITEX_WITH_SPI_SDCARD:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-spi-sdcard)
fi
if [ "${LITEX_WITH_SDCARD:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-sdcard)
fi
if [ "${LITEX_WITH_ETHERNET:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-ethernet)
  EXTRA_LITEX_ARGS+=(--eth-ip "${LITEX_ETH_IP:-192.168.1.50}")
  EXTRA_LITEX_ARGS+=(--remote-ip "${LITEX_REMOTE_IP:-192.168.1.100}")
  if [ "${LITEX_ETH_DYNAMIC_IP:-0}" = "1" ]; then
    EXTRA_LITEX_ARGS+=(--eth-dynamic-ip)
  fi
fi
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# VexRiscvSMP "linux" variant wires sv32 MMU, CLINT, PLIC, and an OpenSBI
# reserved region. hardware-breakpoints=0 selects a pre-generated cluster
# netlist from pythondata-cpu-vexriscv_smp so no SBT/Scala build is needed.
python3 -m litex_boards.targets.digilent_nexys4ddr \
  --cpu-type=vexriscv_smp \
  --cpu-variant=linux \
  --cpu-count="${CPU_COUNT:-1}" \
  --hardware-breakpoints=0 \
  "${EXTRA_LITEX_ARGS[@]}" \
  --build \
  --no-compile \
  --output-dir "$OUT_DIR" \
  --soc-json "$OUT_DIR/csr.json" \
  --soc-csv "$OUT_DIR/csr.csv" \
  --memory-x "$OUT_DIR/memory.x"

python3 third_party/litex/litex/tools/litex_json2dts_linux.py \
  "$OUT_DIR/csr.json" \
  --root-device "${ROOT_DEVICE:-ram0}" \
  > "$OUT_DIR/digilent_nexys4ddr_linux.dts"

# The Nexys4 DDR LedChaser drives all 16 board user LEDs, but litex_json2dts
# defaults litex,ngpio to 4 when the CSR JSON has no leds_ngpio constant. Patch
# the generated &leds node so Linux exposes all 16 LED outputs. Override with
# LITEX_LEDS_NGPIO for boards/variants with a different LED count.
python3 - "$OUT_DIR/digilent_nexys4ddr_linux.dts" "${LITEX_LEDS_NGPIO:-16}" <<'PY'
import re
import sys
from pathlib import Path
path, ngpio = sys.argv[1], int(sys.argv[2])
text = Path(path).read_text()
new, n = re.subn(
    r"(&leds\s*\{.*?litex,ngpio\s*=\s*<)\d+(>)",
    lambda m: m.group(1) + str(ngpio) + m.group(2),
    text,
    count=1,
    flags=re.DOTALL,
)
if n:
    Path(path).write_text(new)
    print(f"Patched &leds litex,ngpio = <{ngpio}>")
else:
    print("warning: &leds litex,ngpio not found; left DTS unchanged", file=sys.stderr)
PY

printf '\nLiteX Nexys4 DDR Linux metadata probe written to %s\n' "$OUT_DIR"
find "$OUT_DIR" -maxdepth 2 -type f \( -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' \) | sort
