#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

SDROOT_DTS=${SDROOT_DTS:-linux/dts/litex_nexys4ddr_vexriscv_smp_sdroot.dts}
SDROOT_DTB=${SDROOT_DTB:-linux/images/rv32_sdroot.dtb}
SDROOT_IMAGES=${SDROOT_IMAGES:-linux/images/litex_vexriscv_smp_sdroot_images.json}

if [ ! -f "$SDROOT_DTS" ]; then
  echo "Missing SD-root DTS: $SDROOT_DTS" >&2
  exit 1
fi

# Build a DTB with SD ext4 root bootargs and no linux,initrd-* patching.
INITRD_IMAGE=none ./scripts/build_litex_dtb.sh "$SDROOT_DTS" "$SDROOT_DTB"

mkdir -p "$(dirname "$SDROOT_IMAGES")"
python3 - "$SDROOT_IMAGES" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
images = {
    "Image": "0x40000000",
    "rv32_sdroot.dtb": "0x40ef0000",
    "opensbi.bin": "0x40f00000",
}
out.write_text(json.dumps(images, indent=2) + "\n", encoding="utf-8")
print(f"SD-root image map: {out}")
PY

for required in linux/images/Image linux/images/opensbi.bin "$SDROOT_DTB"; do
  if [ ! -f "$required" ]; then
    echo "Missing $required. Run scripts/build_buildroot_litex.sh or scripts/collect_litex_linux_images.sh first." >&2
    exit 1
  fi
done
