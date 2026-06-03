# Buildroot

Buildroot is used to build the RV32 Linux kernel image and BusyBox/rootfs artifacts for the LiteX/VexRiscvSMP reference SoC.

The upstream reference flow is `linux-on-litex-vexriscv`, cloned locally by:

```bash
./scripts/bootstrap_linux_on_litex.sh
```

This places the reference trees under ignored `third_party/`:

```text
third_party/linux-on-litex-vexriscv/
third_party/buildroot/
third_party/opensbi/
```

The relevant upstream defconfig is:

```text
third_party/linux-on-litex-vexriscv/buildroot/configs/litex_vexriscv_defconfig
```

It configures:

- RISC-V 32-bit target;
- `rv32ima`, ABI `ilp32`;
- Linux 6.9 plus the Linux-on-LiteX patch set;
- OpenSBI platform `litex/vexriscv`;
- CPIO and ext2 rootfs outputs;
- BusyBox userspace.

## Current address contract

The generated LiteX/VexRiscvSMP DTS expects serial-loaded images at:

```text
Linux Image:  0x40000000
rv32.dtb:      0x40ef0000
rootfs.cpio.gz: 0x41000000
opensbi.bin:  0x40f00000
```

The template image map is:

```text
linux/images/litex_vexriscv_smp_images.example.json
```

## Next command shape

Once ready to build the full Linux/rootfs artifacts:

```bash
./scripts/build_buildroot_litex.sh
```

The generated kernel/rootfs/OpenSBI outputs should then be copied or symlinked into `linux/images/` using the names expected by the image map:

```text
Image
rv32.dtb
rootfs.cpio.gz
opensbi.bin
```

For now, OpenSBI and the DTB can already be built independently with:

```bash
./scripts/build_opensbi_litex.sh
./scripts/build_litex_dtb.sh
```


## Collecting and booting generated images

After Buildroot finishes:

```bash
./scripts/collect_litex_linux_images.sh
```

This populates:

```text
linux/images/Image
linux/images/rootfs.cpio.gz
linux/images/rv32.dtb
linux/images/opensbi.bin
linux/images/litex_vexriscv_smp_images.json
```

Then program/reset the Linux-capable LiteX bitstream and boot over serial:

```bash
./scripts/program_litex_nexys4ddr.sh build/litex_nexys4ddr_linux/gateware/digilent_nexys4ddr.bit
./scripts/boot_litex_linux_serial.sh /dev/ttyUSB1 --safe
```


Note: the helper intentionally unsets `LD_LIBRARY_PATH`, because Buildroot aborts
when the variable contains the current directory or an empty path component.


### Local Linux patch set

The helper uses `local_patches` as Buildroot's `BR2_GLOBAL_PATCH_DIR`. It
mirrors the upstream `linux-on-litex-vexriscv` patch tree, including OpenSBI
patches, but disables the Linux 6.9
`0021-tty-serial-liteuart-use-rx-irqs-when-available.patch` for the initial
Nexys4 DDR bring-up because that backport currently fails to apply to the
downloaded Linux 6.9 tree. LiteUART polling remains sufficient for boot/login;
RX IRQ support can be ported later if interactive input reliability becomes an
issue.

Regenerate the local patch mirror with:

```bash
./scripts/prepare_litex_linux_patches.sh
```


### Nexys4 DDR kernel config

The Buildroot helper overrides the reference kernel config with:

```text
linux/configs/litex_nexys4ddr_linux.config
```

This starts from the upstream `litex_vexriscv` Linux config but disables
`CONFIG_SPI_FLASH_LITEX` for the first serial-boot bring-up. The patched LiteX
SPI flash MTD driver currently references a removed Linux 6.9 `spi_nor` field,
and the Nexys4 DDR serial-loaded Linux path does not need SPI flash yet.


### Nexys4 DDR post-image script

The Buildroot helper overrides the reference `post-image.sh` with:

```text
buildroot/post-image-nexys4ddr.sh
```

The upstream script tries to generate an SD-card image with `genimage` and needs
an upstream `images/boot.json`. For the first Nexys4 DDR bring-up we boot over
LiteX serial loader, so the local post-image script only copies `Image`,
`rootfs.cpio.gz`, and `fw_jump.bin` into `linux/images/`, rebuilds `rv32.dtb`
with an initrd-end matching the compressed image size, and writes
`litex_vexriscv_smp_images.json`.


## Non-interactive serial boot

Use the project wrapper for remote SSH/agent sessions:

```bash
./scripts/boot_litex_linux_serial.sh /dev/ttyUSB1
```

This calls `scripts/serial_boot_litex_images.py`, a small non-interactive LiteX
SFL uploader. It avoids `litex_term`'s requirement for stdin to be a real TTY and
therefore works reliably from background jobs. It also handles the common case
where the board is already at the `litex>` BIOS prompt by sending `serialboot`
before uploading images.

The Linux-capable LiteX bitstream defaults to 1,000,000 baud and the serial
image map now uses `rootfs.cpio.gz`. Progress is printed once per second and the
UART log is written to `/tmp/boot_litex_linux_serial.log` by default. For an
older 115200-baud bitstream, set `LITEX_BAUD=115200` when running the boot
wrapper.
