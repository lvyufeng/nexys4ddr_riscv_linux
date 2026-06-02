# Firmware

Target boot chain:

```text
boot ROM / loader -> OpenSBI -> Linux
```

OpenSBI should run in machine mode and hand off to the Linux kernel in supervisor mode.
