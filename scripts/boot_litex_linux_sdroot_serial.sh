#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

# Serial-load only the kernel, SD-root DTB, and OpenSBI. The root filesystem is
# mounted from the board microSD card's ext4 partition (/dev/mmcblk0p2).
export IMAGES=${IMAGES:-linux/images/litex_vexriscv_smp_sdroot_images.json}
export LITEX_EXIT_ON=${LITEX_EXIT_ON:-litex-sdroot login:}

if [ "$IMAGES" = "linux/images/litex_vexriscv_smp_sdroot_images.json" ] && [ ! -f "$IMAGES" ]; then
  ./scripts/prepare_litex_sdroot_images.sh
fi

exec ./scripts/boot_litex_linux_serial.sh "$@"
