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
