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
EXTRA_LITEX_ARGS=()

# Enable board microSD in SPI mode by default. This keeps the default generated
# csr.json/DTB aligned with linux/dts/litex_nexys4ddr_vexriscv_smp.dts while
# remaining easy to disable for minimal rebuilds.
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

# Enable the Nexys4 DDR RMII Ethernet MAC/PHY path by default for the next
# peripheral milestone. This exposes a normal Linux LiteEth network device when
# the generated DTS and bitstream are used together.
if [ "${LITEX_WITH_ETHERNET:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-ethernet)
  EXTRA_LITEX_ARGS+=(--eth-ip "${LITEX_ETH_IP:-192.168.1.50}")
  EXTRA_LITEX_ARGS+=(--remote-ip "${LITEX_REMOTE_IP:-192.168.1.100}")
  if [ "${LITEX_ETH_DYNAMIC_IP:-0}" = "1" ]; then
    EXTRA_LITEX_ARGS+=(--eth-dynamic-ip)
  fi
fi
mkdir -p "$(dirname "$OUT_DIR")"

python3 -m litex_boards.targets.digilent_nexys4ddr \
  --cpu-type=vexriscv_smp \
  --cpu-variant=linux \
  --cpu-count="${CPU_COUNT:-1}" \
  --hardware-breakpoints=0 \
  --uart-baudrate="$UART_BAUDRATE" \
  "${EXTRA_LITEX_ARGS[@]}" \
  --build \
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

printf '\nLiteX Nexys4 DDR Linux-capable build complete. Output directory: %s\n' "$OUT_DIR"
printf 'LiteX UART baudrate: %s\n' "$UART_BAUDRATE"
printf 'LiteX extra args: %s\n' "${EXTRA_LITEX_ARGS[*]:-(none)}"
find "$OUT_DIR" -maxdepth 4 -type f \( -name '*.bit' -o -name '*.bin' -o -name 'bios.*' -o -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' -o -name '*timing*.rpt' \) | sort
