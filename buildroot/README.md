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
rootfs.cpio:  0x41000000
opensbi.bin:  0x40f00000
```

The template image map is:

```text
linux/images/litex_vexriscv_smp_images.example.json
```

## Next command shape

Once ready to build the full Linux/rootfs artifacts:

```bash
cd third_party/buildroot
make BR2_EXTERNAL=../linux-on-litex-vexriscv/buildroot/ litex_vexriscv_defconfig
make
```

The generated kernel/rootfs/OpenSBI outputs should then be copied or symlinked into `linux/images/` using the names expected by the image map:

```text
Image
rv32.dtb
rootfs.cpio
opensbi.bin
```

For now, OpenSBI and the DTB can already be built independently with:

```bash
./scripts/build_opensbi_litex.sh
./scripts/build_litex_dtb.sh
```
