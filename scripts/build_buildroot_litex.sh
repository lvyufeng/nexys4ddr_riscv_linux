#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

BR_DIR=${BR_DIR:-third_party/buildroot}
BR_EXTERNAL=${BR_EXTERNAL:-../linux-on-litex-vexriscv/buildroot/}
GLOBAL_PATCH_DIR=${GLOBAL_PATCH_DIR:-$ROOT_DIR/local_patches}
LINUX_CONFIG=${LINUX_CONFIG:-$ROOT_DIR/linux/configs/litex_nexys4ddr_linux.config}
POST_IMAGE_SCRIPT=${POST_IMAGE_SCRIPT:-$ROOT_DIR/buildroot/post-image-nexys4ddr.sh}

if [ ! -d "$BR_DIR" ]; then
  echo "Missing $BR_DIR. Run scripts/bootstrap_linux_on_litex.sh first." >&2
  exit 1
fi

if [ ! -d "$GLOBAL_PATCH_DIR" ]; then
  ./scripts/prepare_litex_linux_patches.sh
fi

# Buildroot refuses LD_LIBRARY_PATH entries that reference the current directory
# (including empty path components). Vivado/shell startup files can leave such
# entries behind, so drop LD_LIBRARY_PATH for Buildroot commands.
(
  unset LD_LIBRARY_PATH
  cd "$BR_DIR"
  make BR2_EXTERNAL="$BR_EXTERNAL" litex_vexriscv_defconfig
  if [ -d "$GLOBAL_PATCH_DIR" ]; then
    ./utils/config --file .config --set-str BR2_GLOBAL_PATCH_DIR "$GLOBAL_PATCH_DIR"
  fi
  if [ -f "$LINUX_CONFIG" ]; then
    ./utils/config --file .config --set-str BR2_LINUX_KERNEL_CUSTOM_CONFIG_FILE "$LINUX_CONFIG"
  fi
  if [ -f "$POST_IMAGE_SCRIPT" ]; then
    ./utils/config --file .config --set-str BR2_ROOTFS_POST_IMAGE_SCRIPT "$POST_IMAGE_SCRIPT"
  fi
  make olddefconfig
  make -j"${JOBS:-$(nproc)}"
)
