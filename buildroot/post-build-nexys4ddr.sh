#!/usr/bin/env bash
set -euo pipefail

# Buildroot post-build hook for the Nexys4 DDR image. Runs after the target
# filesystem is assembled (with $TARGET_DIR as the staged rootfs) and before the
# filesystem images are packed.
#
# Add a getty on tty1 so the VGA framebuffer console (fbcon) presents a local
# login prompt. Also add an explicit LiteUART getty on ttyLXU0: with both
# console=liteuart and console=tty0 in the kernel command line, /dev/console can
# resolve to tty0, so Buildroot's default console:: getty alone does not keep a
# login on the serial port. The explicit ttyLXU0 getty keeps serial/SSH as the
# primary control path regardless of which console /dev/console points at.
#
# Idempotent: each line is only appended if absent, so repeated builds and the
# overlay do not accumulate duplicates.

TARGET_DIR=${1:-${TARGET_DIR:-}}
if [ -z "$TARGET_DIR" ]; then
  echo "post-build-nexys4ddr: TARGET_DIR not provided" >&2
  exit 1
fi

INITTAB="$TARGET_DIR/etc/inittab"
TTY1_LINE='tty1::respawn:/sbin/getty -L tty1 0 linux'
SERIAL_LINE='ttyLXU0::respawn:/sbin/getty -L ttyLXU0 0 vt100'

if [ ! -f "$INITTAB" ]; then
  echo "post-build-nexys4ddr: missing $INITTAB" >&2
  exit 1
fi

if grep -qE '^tty1::' "$INITTAB"; then
  echo "post-build-nexys4ddr: tty1 getty already present in inittab"
else
  printf '%s # VGA framebuffer console login\n' "$TTY1_LINE" >> "$INITTAB"
  echo "post-build-nexys4ddr: added tty1 getty for VGA console login"
fi

if grep -qE '^ttyLXU0::' "$INITTAB"; then
  echo "post-build-nexys4ddr: ttyLXU0 getty already present in inittab"
else
  printf '%s # LiteUART serial console login\n' "$SERIAL_LINE" >> "$INITTAB"
  echo "post-build-nexys4ddr: added ttyLXU0 getty for serial control"
fi
