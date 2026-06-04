#!/usr/bin/env bash
set -euo pipefail

# Build the SD-root DTB and image map for the verified 640x480@60Hz VGA framebuffer
# bitstream. This is the VGA sibling of scripts/prepare_litex_sdroot_images.sh: the
# only functional differences in the DTB are the simple-framebuffer + reserved
# framebuffer@47e00000 nodes, the 60 MHz clocks, and the added console=tty0 bootarg
# so the Linux framebuffer console mirrors to the VGA monitor while serial stays
# the primary console. The root filesystem is still the board microSD ext4
# partition (/dev/mmcblk0p2).

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

SDROOT_DTS=${SDROOT_DTS:-linux/dts/litex_nexys4ddr_vexriscv_smp_sdroot_vga_640x480_60mhz.dts}
SDROOT_DTB=${SDROOT_DTB:-linux/images/rv32_sdroot_vga_640x480_60mhz.dtb}
SDROOT_IMAGES=${SDROOT_IMAGES:-linux/images/litex_vexriscv_smp_sdroot_vga_640x480_60mhz_images.json}

if [ ! -f "$SDROOT_DTS" ]; then
  echo "Missing VGA SD-root DTS: $SDROOT_DTS" >&2
  exit 1
fi

# Build a DTB with SD ext4 root bootargs and no linux,initrd-* patching.
INITRD_IMAGE=none ./scripts/build_litex_dtb.sh "$SDROOT_DTS" "$SDROOT_DTB"

mkdir -p "$(dirname "$SDROOT_IMAGES")"
python3 - "$SDROOT_IMAGES" "$(basename "$SDROOT_DTB")" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
dtb_name = sys.argv[2]
images = {
    "Image": "0x40000000",
    dtb_name: "0x40ef0000",
    "opensbi.bin": "0x40f00000",
}
out.write_text(json.dumps(images, indent=2) + "\n", encoding="utf-8")
print(f"VGA SD-root image map: {out}")
PY

for required in linux/images/Image linux/images/opensbi.bin "$SDROOT_DTB"; do
  if [ ! -f "$required" ]; then
    echo "Missing $required. Run scripts/build_buildroot_litex.sh or scripts/collect_litex_linux_images.sh first." >&2
    exit 1
  fi
done
