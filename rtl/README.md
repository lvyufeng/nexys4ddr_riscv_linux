# RTL

RTL is split into:

```text
cpu/    custom RISC-V CPU development
soc/    SoC top-level, bus, boot ROM, memory map integration
perip/  Linux-friendly peripherals: UART, CLINT, PLIC, GPIO, SPI, VGA, etc.
```

The first Linux bring-up may use a reference CPU/SoC generator. Custom RTL should be developed incrementally and verified against the reference Linux path.
