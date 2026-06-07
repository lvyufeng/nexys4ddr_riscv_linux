#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

BUILD_DIR=${BUILD_DIR:-build/litex_nexys4ddr_linux_temp_display}
SRC_DTS=${SRC_DTS:-$BUILD_DIR/digilent_nexys4ddr_linux.dts}
DST_DTS=${DST_DTS:-linux/dts/litex_nexys4ddr_vexriscv_smp_temp_display.dts}
DST_DTB=${DST_DTB:-linux/images/rv32_temp_display.dtb}
IMAGES_JSON=${IMAGES_JSON:-linux/images/litex_vexriscv_smp_temp_display_images.json}
ROOTFS_IMAGE=${ROOTFS_IMAGE:-rootfs.cpio.gz}

if [ ! -f "$SRC_DTS" ]; then
  echo "Missing generated LiteX DTS: $SRC_DTS" >&2
  echo "Build gateware first, e.g.:" >&2
  echo "  LITEX_WITH_XADC=1 LITEX_WITH_TEMP_I2C=1 ./scripts/build_litex_nexys4ddr_linux.sh $BUILD_DIR" >&2
  exit 1
fi
if [ ! -f "linux/images/Image" ]; then
  echo "Missing linux/images/Image; build Buildroot first." >&2
  exit 1
fi
if [ ! -f "linux/images/$ROOTFS_IMAGE" ]; then
  echo "Missing linux/images/$ROOTFS_IMAGE; build Buildroot first." >&2
  exit 1
fi
if [ ! -f "linux/images/opensbi.bin" ]; then
  echo "Missing linux/images/opensbi.bin; build Buildroot first." >&2
  exit 1
fi

mkdir -p "$(dirname "$DST_DTS")" "$(dirname "$DST_DTB")" "$(dirname "$IMAGES_JSON")"
cp "$SRC_DTS" "$DST_DTS"
printf 'copied %s -> %s\n' "$SRC_DTS" "$DST_DTS"

INITRD_IMAGE="linux/images/$ROOTFS_IMAGE" ./scripts/build_litex_dtb.sh "$DST_DTS" "$DST_DTB"

python3 - "$IMAGES_JSON" "$ROOTFS_IMAGE" <<'PY'
from pathlib import Path
import json
import sys
out = Path(sys.argv[1])
rootfs = sys.argv[2]
out.write_text(json.dumps({
    "Image": "0x40000000",
    "rv32_temp_display.dtb": "0x40ef0000",
    rootfs: "0x41000000",
    "opensbi.bin": "0x40f00000",
}, indent=2) + "\n")
PY

printf 'LiteX temperature-display image map: %s\n' "$IMAGES_JSON"
cat "$IMAGES_JSON"
printf '\nTemperature-display Linux images:\n'
ls -lh linux/images/Image "linux/images/$ROOTFS_IMAGE" "$DST_DTB" linux/images/opensbi.bin "$IMAGES_JSON"
