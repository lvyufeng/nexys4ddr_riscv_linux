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
