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
SYS_CLK_FREQ=${LITEX_SYS_CLK_FREQ:-75e6}
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

# Expose RGB LEDs and seven-segment display pins as simple GPIO outputs first;
# richer LED/PWM/display drivers can be layered on after pin-level verification.
if [ "${LITEX_WITH_RGB_LEDS:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-rgb-leds)
fi
if [ "${LITEX_WITH_SEVEN_SEG:-1}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-seven-seg)
fi

# Temperature display sources: FPGA die temperature via XADC/hwmon and the
# Nexys4 DDR board temperature sensor pins via a LiteX bit-banged I2C master.
if [ "${LITEX_WITH_XADC:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-xadc)
fi
if [ "${LITEX_WITH_TEMP_I2C:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-temp-i2c)
fi

# Expose the Nexys4 DDR USB-HID host port through its board-level PS/2 bridge.
# Keep this opt-in so existing VGA-only builds and CSR contracts stay stable.
if [ "${LITEX_WITH_PS2_KEYBOARD:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-ps2-keyboard)
  if [ "${LITEX_WITH_PS2_SELFTEST:-0}" = "1" ]; then
    EXTRA_LITEX_ARGS+=(--with-ps2-selftest)
  fi
fi

# VGA is resource/timing heavier than simple GPIO, so keep it opt-in per build.
# LiteX exposes terminal and framebuffer modes as mutually exclusive target args.
if [ "${LITEX_WITH_VIDEO_TERMINAL:-0}" = "1" ] && [ "${LITEX_WITH_VIDEO_FRAMEBUFFER:-0}" = "1" ]; then
  echo "LITEX_WITH_VIDEO_TERMINAL and LITEX_WITH_VIDEO_FRAMEBUFFER are mutually exclusive." >&2
  exit 1
fi
if [ "${LITEX_WITH_VIDEO_TERMINAL:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-video-terminal)
fi
if [ "${LITEX_WITH_VIDEO_FRAMEBUFFER:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--with-video-framebuffer)
fi
if [ "${LITEX_WITH_VIDEO_TERMINAL:-0}" = "1" ] || [ "${LITEX_WITH_VIDEO_FRAMEBUFFER:-0}" = "1" ]; then
  EXTRA_LITEX_ARGS+=(--video-timing "${LITEX_VIDEO_TIMING:-800x600@60Hz}")
fi
mkdir -p "$(dirname "$OUT_DIR")"

python3 -m "$LITEX_TARGET_MODULE" \
  --cpu-type=vexriscv_smp \
  --cpu-variant=linux \
  --cpu-count="${CPU_COUNT:-1}" \
  --hardware-breakpoints=0 \
  --sys-clk-freq="$SYS_CLK_FREQ" \
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
# node counts default to 4, and local banks that lack upstream DTS emitters are
# inserted from their generated CSR bases. tools/dts_patch_args.py is the single
# source of truth for this contract (shared with the probe script); it also
# discriminates the seven-segment scanner vs legacy GPIOOut layouts.
mapfile -t PATCH_ARGS < <(python3 tools/dts_patch_args.py "$OUT_DIR/csr.json")
if [ "${#PATCH_ARGS[@]}" -eq 0 ]; then
  echo "dts_patch_args.py produced no arguments for $OUT_DIR/csr.json" >&2
  exit 1
fi

python3 tools/patch_litex_nexys4ddr_dts.py "$OUT_DIR/digilent_nexys4ddr_linux.dts" "${PATCH_ARGS[@]}"

# Fail loudly if the generated DTS and the CSR map disagree, rather than shipping
# a DTB whose peripheral addresses or node forms do not match the bitstream.
python3 tools/check_csr_dts_consistency.py \
  "$OUT_DIR/csr.json" "$OUT_DIR/digilent_nexys4ddr_linux.dts"

printf '\nLiteX Nexys4 DDR Linux-capable build complete. Output directory: %s\n' "$OUT_DIR"
printf 'LiteX UART baudrate: %s\n' "$UART_BAUDRATE"
printf 'LiteX extra args: %s\n' "${EXTRA_LITEX_ARGS[*]:-(none)}"
find "$OUT_DIR" -maxdepth 4 -type f \( -name '*.bit' -o -name '*.bin' -o -name 'bios.*' -o -name 'csr.json' -o -name 'csr.csv' -o -name 'memory.x' -o -name '*.dts' -o -name '*timing*.rpt' \) | sort
