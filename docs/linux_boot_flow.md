# Linux boot flow

Target boot chain:

```text
FPGA configuration
  -> reset vector / boot ROM
    -> OpenSBI in M-mode
      -> Linux kernel in S-mode
        -> initramfs / BusyBox
          -> / # shell on UART
```

## Why OpenSBI

Linux expects supervisor binary interface services on RISC-V. OpenSBI handles M-mode firmware responsibilities such as timer services, SBI calls, and handoff to the S-mode kernel.

## Minimum artifacts

```text
firmware/bootrom/      reset/loader path
firmware/opensbi/      OpenSBI build notes or integration
linux/dts/             board device tree
linux/config/          Linux kernel defconfig or notes
buildroot/configs/     rootfs/initramfs config
```

## First UART acceptance

Expected serial output when the minimal platform works:

```text
OpenSBI ...
Platform Name ...
Domain0 Next Address ...
Linux version ...
Run /init as init process
/ #
```

## Early debug checklist

If Linux does not boot:

1. Confirm UART baud and TX pin.
2. Confirm reset vector reaches firmware.
3. Confirm DDR calibration and memory test.
4. Confirm OpenSBI sees expected memory size.
5. Confirm DTS memory base/size matches hardware.
6. Confirm timer interrupt path.
7. Confirm PLIC external interrupt wiring.
8. Confirm kernel is built for the same ISA/ABI as the CPU.


## Current LiteX reference Linux metadata

The LiteX/VexRiscvSMP Linux probe now generates the Linux-facing device tree metadata:

```bash
./scripts/probe_litex_nexys4ddr_linux.sh
```

Reference DTS:

```text
linux/dts/litex_nexys4ddr_vexriscv_smp.dts
```

Confirmed generated platform properties:

```text
CPU:        VexRiscv SMP-LINUX, RV32IMA
MMU:        Sv32
DDR:        0x40000000, 128 MiB
OpenSBI:    0x40f00000, 512 KiB reserved-memory
UART:       LiteUART at 0xf0001000
CLINT:      0xf0010000
PLIC:       0xf0c00000
```

The next boot-flow step is to build OpenSBI/Linux/rootfs artifacts matching this generated DTS instead of the draft custom memory map.


## Serial loader address plan

For the current LiteX/VexRiscvSMP map, load images as:

```text
Linux Image:  0x40000000
rv32.dtb:      0x40ef0000
rootfs.cpio.gz: 0x41000000
OpenSBI image: 0x40f00000
```

Use `linux/images/litex_vexriscv_smp_images.example.json` as the template for `litex_term --images`. Keep OpenSBI last in the JSON object so LiteX jumps to OpenSBI after all images are uploaded.


## OpenSBI-only validation

OpenSBI-only boot has been verified on hardware with the Linux-capable LiteX/VexRiscvSMP bitstream:

```bash
./scripts/build_opensbi_litex.sh
./scripts/build_litex_dtb.sh
./scripts/boot_opensbi_only.sh /dev/ttyUSB1 --safe
```

Expected/observed milestone:

```text
Executing booted program at 0x40f00000
OpenSBI
```

This confirms the M-mode firmware path before adding a Linux kernel and initramfs.


Before re-running this smoke test after a successful OpenSBI jump, reprogram the Linux-capable LiteX bitstream or press the FPGA reset button so the LiteX BIOS boot menu is emitted again. The automatic `--serial-boot` handshake is emitted by the LiteX BIOS during the short boot window, not by OpenSBI. If the board is already at the `litex>` prompt, the manual command is `serialboot`, but automation can miss its short magic prompt.
