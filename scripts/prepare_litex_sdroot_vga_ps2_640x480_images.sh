#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

SDROOT_DTS=${SDROOT_DTS:-linux/dts/litex_nexys4ddr_vexriscv_smp_sdroot_vga_ps2_640x480_60mhz.dts}
SDROOT_DTB=${SDROOT_DTB:-linux/images/rv32_sdroot_vga_ps2_640x480_60mhz.dtb}
IMAGES_JSON=${IMAGES_JSON:-linux/images/litex_vexriscv_smp_sdroot_vga_ps2_640x480_60mhz_images.json}

INITRD_IMAGE=none ./scripts/build_litex_dtb.sh "$SDROOT_DTS" "$SDROOT_DTB"

cat > "$IMAGES_JSON" <<'JSON'
{
  "Image": "0x40000000",
  "rv32_sdroot_vga_ps2_640x480_60mhz.dtb": "0x40ef0000",
  "opensbi.bin": "0x40f00000"
}
JSON

printf 'LiteX VGA+PS/2 SD-root image map: %s\n' "$IMAGES_JSON"
cat "$IMAGES_JSON"
