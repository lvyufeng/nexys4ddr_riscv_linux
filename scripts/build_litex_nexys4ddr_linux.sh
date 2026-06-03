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
LITEX_TARGET_MODULE=${LITEX_TARGET_MODULE:-litex_targets.nexys4ddr_linux}
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

# Expose the board switches/buttons as LiteX GPIO input controllers. These come
# from the checked-in litex_targets wrapper, not the upstream target, so they are
# only available when LITEX_TARGET_MODULE points at the local module.
if [ "${LITEX_WITH_SWITCHES:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-switches)
fi
if [ "${LITEX_WITH_BUTTONS:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-buttons)
fi
mkdir -p "$(dirname "$OUT_DIR")"

python3 -m "$LITEX_TARGET_MODULE" \
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

# Patch GPIO metadata that litex_json2dts cannot infer: the LedChaser/switch GPIO
# node counts default to 4, and the local buttons GPIO input has no upstream DTS
# emitter. tools/patch_litex_nexys4ddr_dts.py fixes ngpio counts and inserts the
# buttons node from the generated CSR base/interrupt.
PATCH_ARGS=(--leds-ngpio "${LITEX_LEDS_NGPIO:-16}" --switches-ngpio "${LITEX_SWITCHES_NGPIO:-16}" --buttons-ngpio "${LITEX_BUTTONS_NGPIO:-5}")
BUTTONS_META=$(python3 - "$OUT_DIR/csr.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
base = d.get("csr_bases", {}).get("buttons")
intr = d.get("constants", {}).get("buttons_interrupt")
print(f"0x{base:x}" if base is not None else "")
print(intr if intr is not None else "")
PY
)
BUTTONS_BASE=$(printf '%s\n' "$BUTTONS_META" | sed -n '1p')
BUTTONS_INTERRUPT=$(printf '%s\n' "$BUTTONS_META" | sed -n '2p')
if [ -n "$BUTTONS_BASE" ]; then
  PATCH_ARGS+=(--buttons-base "$BUTTONS_BASE")
fi
if [ -n "$BUTTONS_INTERRUPT" ]; then
  PATCH_ARGS+=(--buttons-interrupt "$BUTTONS_INTERRUPT")
fi
python3 tools/patch_litex_nexys4ddr_dts.py "$OUT_DIR/digilent_nexys4ddr_linux.dts" "${PATCH_ARGS[@]}"

printf '\nLiteX Nexys4 DDR Linux-capable build complete. Output directory: %s\n' "$OUT_DIR"
printf 'LiteX UART baudrate: %s\n' "$UART_BAUDRATE"
printf 'LiteX extra args: %s\n' "${EXTRA_LITEX_ARGS[*]:-(none)}"
find "$OUT_DIR" -maxdepth 4 -type f \( -name '*.bit' -o -name '*.bin' -o -name 'bios.*' -o -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' -o -name '*timing*.rpt' \) | sort
