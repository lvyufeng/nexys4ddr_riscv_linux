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
LITEX_TARGET_MODULE=${LITEX_TARGET_MODULE:-litex_targets.nexys4ddr_linux}
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

# Keep Ethernet enabled by default so probe metadata matches the verified SD-root
# network platform unless explicitly disabled for a smaller experiment.
if [ "${LITEX_WITH_ETHERNET:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-ethernet)
  EXTRA_LITEX_ARGS+=(--eth-ip "${LITEX_ETH_IP:-192.168.1.50}")
  EXTRA_LITEX_ARGS+=(--remote-ip "${LITEX_REMOTE_IP:-192.168.1.100}")
  if [ "${LITEX_ETH_DYNAMIC_IP:-0}" = "1" ]; then
    EXTRA_LITEX_ARGS+=(--eth-dynamic-ip)
  fi
fi

# Expose the board switches/buttons as LiteX GPIO input controllers through the
# checked-in local LiteX target wrapper.
if [ "${LITEX_WITH_SWITCHES:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-switches)
fi
if [ "${LITEX_WITH_BUTTONS:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-buttons)
fi
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# VexRiscvSMP "linux" variant wires sv32 MMU, CLINT, PLIC, and an OpenSBI
# reserved region. hardware-breakpoints=0 selects a pre-generated cluster
# netlist from pythondata-cpu-vexriscv_smp so no SBT/Scala build is needed.
python3 -m "$LITEX_TARGET_MODULE" \
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

# Patch GPIO metadata that litex_json2dts cannot infer: the LedChaser/switch GPIO
# node counts default to 4, and the local buttons GPIO input has no upstream DTS
# emitter. tools/patch_litex_nexys4ddr_dts.py fixes ngpio counts and inserts the
# buttons node from the generated CSR base.
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

printf '\nLiteX Nexys4 DDR Linux metadata probe written to %s\n' "$OUT_DIR"
find "$OUT_DIR" -maxdepth 2 -type f \( -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' \) | sort
