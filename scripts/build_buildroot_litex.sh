#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

BR_DIR=${BR_DIR:-third_party/buildroot}
BR_EXTERNAL=${BR_EXTERNAL:-../linux-on-litex-vexriscv/buildroot/}
GLOBAL_PATCH_DIR=${GLOBAL_PATCH_DIR:-$ROOT_DIR/local_patches}
LINUX_CONFIG=${LINUX_CONFIG:-$ROOT_DIR/linux/configs/litex_nexys4ddr_linux.config}
POST_IMAGE_SCRIPT=${POST_IMAGE_SCRIPT:-$ROOT_DIR/buildroot/post-image-nexys4ddr.sh}
POST_BUILD_SCRIPT=${POST_BUILD_SCRIPT:-$ROOT_DIR/buildroot/post-build-nexys4ddr.sh}
ROOTFS_OVERLAY=${ROOTFS_OVERLAY:-$ROOT_DIR/buildroot/overlay}

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
  # Rootfs overlay + post-build hook for the VGA framebuffer console: the overlay
  # ships /etc/init.d/S09litex-vga (enables the LiteX video DMA/VTG so fbcon is
  # visible), and the post-build script adds a tty1 getty for on-screen login.
  # Both are no-ops on non-VGA bitstreams (S09litex-vga keys off /dev/fb0).
  if [ -d "$ROOTFS_OVERLAY" ]; then
    ./utils/config --file .config --set-str BR2_ROOTFS_OVERLAY "$ROOTFS_OVERLAY"
  fi
  if [ -f "$POST_BUILD_SCRIPT" ]; then
    ./utils/config --file .config --set-str BR2_ROOTFS_POST_BUILD_SCRIPT "$POST_BUILD_SCRIPT"
  fi
  # Enable SSH access for the Ethernet milestone. Dropbear rejects empty-password
  # root logins by default, so give the lab image a simple configurable password.
  # Override with BR_ROOT_PASSWORD=... for a different local password.
  ./utils/config --file .config --enable BR2_PACKAGE_DROPBEAR
  ./utils/config --file .config --set-str BR2_TARGET_GENERIC_ROOT_PASSWD "${BR_ROOT_PASSWORD:-root}"

  # Install libgpiod command-line tools so board GPIO peripherals can be exercised
  # directly from the SD-root shell/SSH session (gpioinfo/gpioset/gpioget).
  ./utils/config --file .config --enable BR2_PACKAGE_LIBGPIOD
  ./utils/config --file .config --enable BR2_PACKAGE_LIBGPIOD_TOOLS

  # Keep the serial-loaded initramfs compact. At 115200 baud, the raw CPIO
  # rootfs dominates upload time; gzip typically cuts it by several MiB and is
  # supported by the kernel config via CONFIG_RD_GZIP=y.
  ./utils/config --file .config --enable BR2_TARGET_ROOTFS_CPIO
  ./utils/config --file .config --disable BR2_TARGET_ROOTFS_CPIO_NONE
  ./utils/config --file .config --enable BR2_TARGET_ROOTFS_CPIO_GZIP
  make olddefconfig
  make -j"${JOBS:-$(nproc)}"
)
