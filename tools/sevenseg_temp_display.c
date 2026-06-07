#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <linux/i2c-dev.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define DIGITS 8
#define GROUP_DIGITS 4
#define DEFAULT_CSR_BASE 0xf0006800UL
#define DEFAULT_XADC_CSR_BASE 0xf0009800UL
#define DEFAULT_TEMP_I2C_CSR_BASE 0xf000a000UL
#define DEFAULT_CSR_DEVICE "/dev/mem"
#define DEFAULT_HWMON_NAME "litex_xadc"
#define DEFAULT_I2C_BUS "/dev/i2c-0"
#define DEFAULT_I2C_ADDR 0x4b
#define DEFAULT_SCAN_HZ 1000U
#define DEFAULT_SYS_CLK_HZ 75000000U
#define DEFAULT_I2C_DELAY_US 50U

#define CSR_CONTROL_OFFSET 0x00
#define CSR_DIGIT0_OFFSET  0x04
#define CSR_STATUS_OFFSET  0x24

static volatile sig_atomic_t stop_requested;

struct cell {
    char ch;
    int dp;
};

struct csr_map {
    int fd;
    unsigned long base;
    unsigned long page_base;
    unsigned long page_offset;
    size_t map_size;
    volatile uint8_t *mem;
};

struct options {
    const char *csr_device;
    unsigned long csr_base;
    unsigned long xadc_csr_base;
    unsigned long temp_i2c_csr_base;
    const char *hwmon_name;
    const char *ambient_i2c_bus;
    unsigned int ambient_i2c_addr;
    long update_ms;
    int segments_active_low;
    int reverse_digits;
    int fake;
    long fake_fpga_mc;
    long fake_ambient_mc;
    unsigned int scan_hz;
    unsigned int sys_clk_hz;
    unsigned int i2c_delay_us;
    int no_raw_fallback;
};

static void handle_signal(int sig) {
    (void)sig;
    stop_requested = 1;
}

static void sleep_ms(long ms) {
    if (ms < 0)
        ms = 0;
    struct timespec ts;
    ts.tv_sec = ms / 1000L;
    ts.tv_nsec = (ms % 1000L) * 1000000L;
    while (nanosleep(&ts, &ts) < 0 && errno == EINTR && !stop_requested) {
    }
}

static long monotonic_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static int parse_u32(const char *s, unsigned int *out) {
    char *end = NULL;
    errno = 0;
    unsigned long v = strtoul(s, &end, 0);
    if (errno || end == s || *end || v > 0xfffffffful)
        return -1;
    *out = (unsigned int)v;
    return 0;
}

static int parse_ulong(const char *s, unsigned long *out) {
    char *end = NULL;
    errno = 0;
    unsigned long v = strtoul(s, &end, 0);
    if (errno || end == s || *end)
        return -1;
    *out = v;
    return 0;
}

static int parse_temp_mc(const char *s, long *out_mc) {
    char *end = NULL;
    errno = 0;
    double v = strtod(s, &end);
    if (errno || end == s || *end)
        return -1;
    double mc = v * 1000.0;
    *out_mc = (long)(mc >= 0 ? mc + 0.5 : mc - 0.5);
    return 0;
}

static int parse_fake_pair(const char *s, long *a_mc, long *b_mc) {
    const char *comma = strchr(s, ',');
    if (!comma)
        return -1;
    char left[64], right[64];
    size_t n = (size_t)(comma - s);
    if (n >= sizeof(left) || strlen(comma + 1) >= sizeof(right))
        return -1;
    memcpy(left, s, n);
    left[n] = 0;
    strcpy(right, comma + 1);
    if (parse_temp_mc(left, a_mc) < 0)
        return -1;
    if (parse_temp_mc(right, b_mc) < 0)
        return -1;
    return 0;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "usage: %s [options]\n"
        "\n"
        "Display FPGA and ambient temperatures on the Nexys4 DDR 8-digit seven-seg display.\n"
        "This version uses the LiteX hardware seven-segment scanner CSR, so Linux only\n"
        "updates segment bytes at low rate and the FPGA performs flicker-free multiplexing.\n"
        "\n"
        "Options:\n"
        "  --csr-device PATH        memory device for CSR mmap (default " DEFAULT_CSR_DEVICE ")\n"
        "  --csr-base ADDR          seven_seg scanner CSR base (default 0x%08lx)\n"
        "  --xadc-csr-base ADDR     raw XADC CSR base fallback (default 0x%08lx)\n"
        "  --temp-i2c-csr-base ADDR raw LiteX I2C CSR base fallback (default 0x%08lx)\n"
        "  --fpga-hwmon-name NAME   hwmon name for FPGA XADC (default " DEFAULT_HWMON_NAME ")\n"
        "  --ambient-i2c-bus PATH   I2C bus for board temperature sensor (default " DEFAULT_I2C_BUS ")\n"
        "  --ambient-i2c-addr ADDR  I2C address, e.g. 0x4b (default 0x%02x)\n"
        "  --update-ms MSEC         sensor/display update interval (default 500)\n"
        "  --scan-hz HZ             full-display scan rate programmed into FPGA (default %u)\n"
        "  --sys-clk-hz HZ          LiteX sys_clk for scan divider (default %u)\n"
        "  --i2c-delay-us USEC      raw CSR I2C half-period delay (default %u)\n"
        "  --no-raw-fallback        do not use /dev/mem XADC/I2C sensor fallback\n"
        "  --segments-active-low    invert segment GPIO values in hardware scanner (default)\n"
        "  --segments-active-high   use raw active-high segment masks\n"
        "  --reverse-digits         map display left-to-right to digit lines 7..0 (default)\n"
        "  --no-reverse-digits      map display left-to-right to digit lines 0..7\n"
        "  --fake A,B               display fake temperatures, e.g. --fake 42.3,25.6\n"
        "  --help                   show this help\n",
        prog, DEFAULT_CSR_BASE, DEFAULT_XADC_CSR_BASE, DEFAULT_TEMP_I2C_CSR_BASE,
        DEFAULT_I2C_ADDR, DEFAULT_SCAN_HZ, DEFAULT_SYS_CLK_HZ, DEFAULT_I2C_DELAY_US);
}

static int csr_open(struct csr_map *m, const char *device, unsigned long base, size_t span) {
    memset(m, 0, sizeof(*m));
    m->fd = -1;
    m->base = base;
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0)
        page = 4096;
    m->page_base = base & ~((unsigned long)page - 1);
    m->page_offset = base - m->page_base;
    m->map_size = m->page_offset + span;

    m->fd = open(device, O_RDWR | O_SYNC | O_CLOEXEC);
    if (m->fd < 0) {
        fprintf(stderr, "open %s failed: %s\n", device, strerror(errno));
        return -1;
    }
    void *ptr = mmap(NULL, m->map_size, PROT_READ | PROT_WRITE, MAP_SHARED, m->fd, (off_t)m->page_base);
    if (ptr == MAP_FAILED) {
        fprintf(stderr, "mmap %s at 0x%lx failed: %s\n", device, base, strerror(errno));
        close(m->fd);
        m->fd = -1;
        return -1;
    }
    m->mem = (volatile uint8_t *)ptr;
    return 0;
}

static void csr_close(struct csr_map *m) {
    if (m->mem)
        munmap((void *)m->mem, m->map_size);
    if (m->fd >= 0)
        close(m->fd);
    m->mem = NULL;
    m->fd = -1;
}

static uint32_t csr_read32(const struct csr_map *m, unsigned int offset) {
    volatile uint32_t *reg = (volatile uint32_t *)(m->mem + m->page_offset + offset);
    uint32_t value = *reg;
    __sync_synchronize();
    return value;
}

static void csr_write32(const struct csr_map *m, unsigned int offset, uint32_t value) {
    volatile uint32_t *reg = (volatile uint32_t *)(m->mem + m->page_offset + offset);
    *reg = value;
    __sync_synchronize();
}

static uint32_t scanner_control_value(const struct options *opt, int enable) {
    unsigned int scan_hz = opt->scan_hz ? opt->scan_hz : DEFAULT_SCAN_HZ;
    unsigned int divider = opt->sys_clk_hz / (scan_hz * DIGITS);
    if (divider < 1)
        divider = 1;
    if (divider > 0x00ffffffu)
        divider = 0x00ffffffu;
    return ((uint32_t)divider << 8) |
           (opt->reverse_digits ? (1u << 2) : 0) |
           (opt->segments_active_low ? (1u << 1) : 0) |
           (enable ? 1u : 0u);
}

static void scanner_blank(const struct csr_map *m, const struct options *opt) {
    csr_write32(m, CSR_CONTROL_OFFSET, scanner_control_value(opt, 0));
    for (int i = 0; i < DIGITS; i++)
        csr_write32(m, CSR_DIGIT0_OFFSET + (unsigned int)i * 4u, 0x00);
}

static void scanner_write_cells(const struct csr_map *m, const struct options *opt, const struct cell cells[DIGITS]);

static unsigned int glyph_mask(char ch) {
    switch (ch) {
    case '0': return 0x3f;
    case '1': return 0x06;
    case '2': return 0x5b;
    case '3': return 0x4f;
    case '4': return 0x66;
    case '5': return 0x6d;
    case '6': return 0x7d;
    case '7': return 0x07;
    case '8': return 0x7f;
    case '9': return 0x6f;
    case '-': return 0x40;
    case 'C':
    case 'c': return 0x39;
    default:  return 0x00;
    }
}

static unsigned int cell_to_segments(struct cell c) {
    unsigned int mask = glyph_mask(c.ch);
    if (c.dp)
        mask |= 0x80;
    return mask & 0xff;
}

static int format_temp_group(long mc, struct cell out[GROUP_DIGITS]) {
    for (int i = 0; i < GROUP_DIGITS; i++) {
        out[i].ch = ' ';
        out[i].dp = 0;
    }

    long tenths = (mc >= 0) ? (mc + 50) / 100 : (mc - 50) / 100;
    long abs_tenths = tenths >= 0 ? tenths : -tenths;
    long whole = abs_tenths / 10;
    long frac = abs_tenths % 10;

    char text[32];
    if (tenths < 0)
        snprintf(text, sizeof(text), "-%ld.%ld", whole, frac);
    else
        snprintf(text, sizeof(text), "%ld.%ld", whole, frac);

    struct cell tmp[GROUP_DIGITS];
    int count = 0;
    for (const char *p = text; *p; p++) {
        if (*p == '.') {
            if (count == 0)
                return -1;
            tmp[count - 1].dp = 1;
            continue;
        }
        if (count >= GROUP_DIGITS)
            return -1;
        tmp[count].ch = *p;
        tmp[count].dp = 0;
        count++;
    }

    int pad = GROUP_DIGITS - count;
    for (int i = 0; i < count; i++)
        out[pad + i] = tmp[i];
    return 0;
}

static void format_missing_group(struct cell out[GROUP_DIGITS]) {
    for (int i = 0; i < GROUP_DIGITS; i++) {
        out[i].ch = '-';
        out[i].dp = 0;
    }
}

static int read_file_trim(const char *path, char *buf, size_t len) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return -1;
    ssize_t n = read(fd, buf, len - 1);
    close(fd);
    if (n <= 0)
        return -1;
    buf[n] = 0;
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r' || buf[n - 1] == ' ' || buf[n - 1] == '\t'))
        buf[--n] = 0;
    return 0;
}

static int read_fpga_temp_mc(const char *hwmon_name, long *mc) {
    glob_t g;
    memset(&g, 0, sizeof(g));
    if (glob("/sys/class/hwmon/hwmon*", 0, NULL, &g) != 0)
        return -1;

    int ret = -1;
    for (size_t i = 0; i < g.gl_pathc && ret < 0; i++) {
        char path[512], name[128], val[128];
        snprintf(path, sizeof(path), "%s/name", g.gl_pathv[i]);
        if (read_file_trim(path, name, sizeof(name)) < 0)
            continue;
        if (strcmp(name, hwmon_name) != 0)
            continue;
        snprintf(path, sizeof(path), "%s/temp1_input", g.gl_pathv[i]);
        if (read_file_trim(path, val, sizeof(val)) < 0)
            continue;
        char *end = NULL;
        errno = 0;
        long v = strtol(val, &end, 10);
        if (!errno && end != val && *end == 0) {
            *mc = v;
            ret = 0;
        }
    }
    globfree(&g);
    return ret;
}

static int i2c_read_reg8(int fd, unsigned int reg, unsigned int *val) {
    uint8_t r = reg & 0xff;
    if (write(fd, &r, 1) != 1)
        return -1;
    uint8_t v = 0;
    if (read(fd, &v, 1) != 1)
        return -1;
    *val = v;
    return 0;
}

static int i2c_read_reg16_be(int fd, unsigned int reg, unsigned int *val) {
    uint8_t r = reg & 0xff;
    if (write(fd, &r, 1) != 1)
        return -1;
    uint8_t b[2];
    if (read(fd, b, 2) != 2)
        return -1;
    *val = ((unsigned int)b[0] << 8) | b[1];
    return 0;
}

static int sign_extend(int value, int bits) {
    int shift = (int)(sizeof(int) * 8) - bits;
    return (value << shift) >> shift;
}

static long adt7420_raw_to_mc(unsigned int cfg, unsigned int raw) {
    if (cfg & 0x80) {
        int v = sign_extend((int)raw, 16);
        return (long)((v * 1000) / 128);
    }
    int v = sign_extend((int)(raw >> 3), 13);
    return (long)((v * 1000) / 16);
}

static int read_adt7420_temp_mc(const char *bus, unsigned int addr, long *mc) {
    int fd = open(bus, O_RDWR | O_CLOEXEC);
    if (fd < 0)
        return -1;
    if (ioctl(fd, I2C_SLAVE, addr) < 0) {
        close(fd);
        return -1;
    }

    unsigned int cfg = 0, raw = 0;
    if (i2c_read_reg8(fd, 0x03, &cfg) < 0 || i2c_read_reg16_be(fd, 0x00, &raw) < 0) {
        close(fd);
        return -1;
    }
    close(fd);

    *mc = adt7420_raw_to_mc(cfg, raw);
    return 0;
}

static int read_raw_xadc_temp_mc(const struct options *opt, long *mc) {
    struct csr_map xadc;
    if (csr_open(&xadc, opt->csr_device, opt->xadc_csr_base, 0x18) < 0)
        return -1;

    unsigned int raw = csr_read32(&xadc, 0x00) & 0x0fff;
    csr_close(&xadc);

    if (raw == 0 || raw == 0x0fff)
        return -1;
    unsigned long long scaled = ((unsigned long long)raw * 503975ULL) / 4096ULL;
    *mc = (long)scaled - 273150L;
    return 0;
}

#define LITEX_I2C_W_OFFSET 0x00
#define LITEX_I2C_R_OFFSET 0x04
#define LITEX_I2C_SCL      (1u << 0)
#define LITEX_I2C_SDA_DIR  (1u << 1)
#define LITEX_I2C_SDA_W    (1u << 2)

struct raw_i2c {
    struct csr_map map;
    uint32_t w;
    unsigned int delay_us;
};

static void raw_i2c_delay(const struct raw_i2c *bus) {
    if (bus->delay_us)
        usleep(bus->delay_us);
}

static void raw_i2c_write_w(struct raw_i2c *bus) {
    csr_write32(&bus->map, LITEX_I2C_W_OFFSET, bus->w);
}

static void raw_i2c_set_scl(struct raw_i2c *bus, int high) {
    if (high)
        bus->w |= LITEX_I2C_SCL;
    else
        bus->w &= ~LITEX_I2C_SCL;
    raw_i2c_write_w(bus);
    raw_i2c_delay(bus);
}

static void raw_i2c_drive_sda(struct raw_i2c *bus, int high) {
    bus->w |= LITEX_I2C_SDA_DIR;
    if (high)
        bus->w |= LITEX_I2C_SDA_W;
    else
        bus->w &= ~LITEX_I2C_SDA_W;
    raw_i2c_write_w(bus);
    raw_i2c_delay(bus);
}

static void raw_i2c_release_sda(struct raw_i2c *bus) {
    bus->w &= ~LITEX_I2C_SDA_DIR;
    raw_i2c_write_w(bus);
    raw_i2c_delay(bus);
}

static int raw_i2c_read_sda(struct raw_i2c *bus) {
    raw_i2c_release_sda(bus);
    return (csr_read32(&bus->map, LITEX_I2C_R_OFFSET) & 1u) ? 1 : 0;
}

static void raw_i2c_init_bus(struct raw_i2c *bus) {
    bus->w = 0;
    raw_i2c_write_w(bus);
    raw_i2c_release_sda(bus);
    raw_i2c_set_scl(bus, 1);
}

static void raw_i2c_start(struct raw_i2c *bus) {
    raw_i2c_release_sda(bus);
    raw_i2c_set_scl(bus, 1);
    raw_i2c_drive_sda(bus, 0);
    raw_i2c_set_scl(bus, 0);
}

static void raw_i2c_stop(struct raw_i2c *bus) {
    raw_i2c_drive_sda(bus, 0);
    raw_i2c_set_scl(bus, 1);
    raw_i2c_release_sda(bus);
}

static int raw_i2c_write_byte(struct raw_i2c *bus, unsigned int byte) {
    for (int bit = 7; bit >= 0; bit--) {
        raw_i2c_set_scl(bus, 0);
        if (byte & (1u << bit))
            raw_i2c_release_sda(bus);
        else
            raw_i2c_drive_sda(bus, 0);
        raw_i2c_set_scl(bus, 1);
    }
    raw_i2c_set_scl(bus, 0);
    raw_i2c_release_sda(bus);
    raw_i2c_set_scl(bus, 1);
    int ack = (raw_i2c_read_sda(bus) == 0);
    raw_i2c_set_scl(bus, 0);
    return ack ? 0 : -1;
}

static int raw_i2c_read_byte(struct raw_i2c *bus, int ack) {
    unsigned int byte = 0;
    raw_i2c_release_sda(bus);
    for (int bit = 7; bit >= 0; bit--) {
        raw_i2c_set_scl(bus, 0);
        raw_i2c_release_sda(bus);
        raw_i2c_set_scl(bus, 1);
        if (raw_i2c_read_sda(bus))
            byte |= 1u << bit;
    }
    raw_i2c_set_scl(bus, 0);
    if (ack)
        raw_i2c_drive_sda(bus, 0);
    else
        raw_i2c_release_sda(bus);
    raw_i2c_set_scl(bus, 1);
    raw_i2c_set_scl(bus, 0);
    raw_i2c_release_sda(bus);
    return (int)(byte & 0xffu);
}

static int raw_i2c_read_reg(struct raw_i2c *bus, unsigned int addr, unsigned int reg,
                            uint8_t *buf, size_t len) {
    if (len == 0)
        return 0;

    raw_i2c_start(bus);
    if (raw_i2c_write_byte(bus, (addr << 1) | 0u) < 0)
        goto fail;
    if (raw_i2c_write_byte(bus, reg & 0xffu) < 0)
        goto fail;
    raw_i2c_start(bus);
    if (raw_i2c_write_byte(bus, (addr << 1) | 1u) < 0)
        goto fail;
    for (size_t i = 0; i < len; i++)
        buf[i] = (uint8_t)raw_i2c_read_byte(bus, i + 1 < len);
    raw_i2c_stop(bus);
    return 0;

fail:
    raw_i2c_stop(bus);
    return -1;
}

static int read_raw_adt7420_temp_mc(const struct options *opt, long *mc) {
    struct raw_i2c bus;
    memset(&bus, 0, sizeof(bus));
    bus.delay_us = opt->i2c_delay_us ? opt->i2c_delay_us : DEFAULT_I2C_DELAY_US;
    if (csr_open(&bus.map, opt->csr_device, opt->temp_i2c_csr_base, 0x08) < 0)
        return -1;

    raw_i2c_init_bus(&bus);
    uint8_t cfg = 0;
    uint8_t temp[2] = {0, 0};
    int ret = 0;
    if (raw_i2c_read_reg(&bus, opt->ambient_i2c_addr, 0x03, &cfg, 1) < 0 ||
        raw_i2c_read_reg(&bus, opt->ambient_i2c_addr, 0x00, temp, 2) < 0) {
        ret = -1;
    } else {
        unsigned int raw = ((unsigned int)temp[0] << 8) | temp[1];
        *mc = adt7420_raw_to_mc(cfg, raw);
    }
    raw_i2c_stop(&bus);
    csr_close(&bus.map);
    return ret;
}

static void build_display_cells(const struct options *opt, struct cell cells[DIGITS]) {
    long fpga_mc = 0, ambient_mc = 0;
    int have_fpga = 0, have_ambient = 0;

    if (opt->fake) {
        fpga_mc = opt->fake_fpga_mc;
        ambient_mc = opt->fake_ambient_mc;
        have_fpga = have_ambient = 1;
    } else {
        have_fpga = (read_fpga_temp_mc(opt->hwmon_name, &fpga_mc) == 0);
        if (!have_fpga && !opt->no_raw_fallback)
            have_fpga = (read_raw_xadc_temp_mc(opt, &fpga_mc) == 0);

        have_ambient = (read_adt7420_temp_mc(opt->ambient_i2c_bus, opt->ambient_i2c_addr, &ambient_mc) == 0);
        if (!have_ambient && !opt->no_raw_fallback)
            have_ambient = (read_raw_adt7420_temp_mc(opt, &ambient_mc) == 0);
    }

    if (!have_fpga || format_temp_group(fpga_mc, &cells[0]) < 0)
        format_missing_group(&cells[0]);
    if (!have_ambient || format_temp_group(ambient_mc, &cells[GROUP_DIGITS]) < 0)
        format_missing_group(&cells[GROUP_DIGITS]);
}

static void scanner_write_cells(const struct csr_map *m, const struct options *opt, const struct cell cells[DIGITS]) {
    for (int i = 0; i < DIGITS; i++)
        csr_write32(m, CSR_DIGIT0_OFFSET + (unsigned int)i * 4u, cell_to_segments(cells[i]));
    csr_write32(m, CSR_CONTROL_OFFSET, scanner_control_value(opt, 1));
}

static int parse_args(int argc, char **argv, struct options *opt) {
    opt->csr_device = DEFAULT_CSR_DEVICE;
    opt->csr_base = DEFAULT_CSR_BASE;
    opt->xadc_csr_base = DEFAULT_XADC_CSR_BASE;
    opt->temp_i2c_csr_base = DEFAULT_TEMP_I2C_CSR_BASE;
    opt->hwmon_name = DEFAULT_HWMON_NAME;
    opt->ambient_i2c_bus = DEFAULT_I2C_BUS;
    opt->ambient_i2c_addr = DEFAULT_I2C_ADDR;
    opt->update_ms = 500;
    opt->segments_active_low = 1;
    opt->reverse_digits = 1;
    opt->fake = 0;
    opt->fake_fpga_mc = 42300;
    opt->fake_ambient_mc = 25600;
    opt->scan_hz = DEFAULT_SCAN_HZ;
    opt->sys_clk_hz = DEFAULT_SYS_CLK_HZ;
    opt->i2c_delay_us = DEFAULT_I2C_DELAY_US;
    opt->no_raw_fallback = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--help")) {
            usage(argv[0]);
            exit(0);
        } else if (!strcmp(argv[i], "--csr-device") && i + 1 < argc) {
            opt->csr_device = argv[++i];
        } else if (!strcmp(argv[i], "--csr-base") && i + 1 < argc) {
            if (parse_ulong(argv[++i], &opt->csr_base) < 0) {
                fprintf(stderr, "invalid CSR base\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--xadc-csr-base") && i + 1 < argc) {
            if (parse_ulong(argv[++i], &opt->xadc_csr_base) < 0) {
                fprintf(stderr, "invalid XADC CSR base\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--temp-i2c-csr-base") && i + 1 < argc) {
            if (parse_ulong(argv[++i], &opt->temp_i2c_csr_base) < 0) {
                fprintf(stderr, "invalid temp I2C CSR base\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--fpga-hwmon-name") && i + 1 < argc) {
            opt->hwmon_name = argv[++i];
        } else if (!strcmp(argv[i], "--ambient-i2c-bus") && i + 1 < argc) {
            opt->ambient_i2c_bus = argv[++i];
        } else if (!strcmp(argv[i], "--ambient-i2c-addr") && i + 1 < argc) {
            if (parse_u32(argv[++i], &opt->ambient_i2c_addr) < 0 || opt->ambient_i2c_addr > 0x7f) {
                fprintf(stderr, "invalid I2C address\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--update-ms") && i + 1 < argc) {
            opt->update_ms = strtol(argv[++i], NULL, 0);
            if (opt->update_ms < 50)
                opt->update_ms = 50;
        } else if (!strcmp(argv[i], "--refresh-us") && i + 1 < argc) {
            /* Compatibility with the older GPIO-scanning helper. Hardware scan
             * refresh is controlled by --scan-hz; consume and ignore this. */
            i++;
        } else if (!strcmp(argv[i], "--scan-hz") && i + 1 < argc) {
            if (parse_u32(argv[++i], &opt->scan_hz) < 0 || opt->scan_hz == 0) {
                fprintf(stderr, "invalid scan hz\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--sys-clk-hz") && i + 1 < argc) {
            if (parse_u32(argv[++i], &opt->sys_clk_hz) < 0 || opt->sys_clk_hz == 0) {
                fprintf(stderr, "invalid sys clk hz\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--i2c-delay-us") && i + 1 < argc) {
            if (parse_u32(argv[++i], &opt->i2c_delay_us) < 0 || opt->i2c_delay_us == 0) {
                fprintf(stderr, "invalid i2c delay\n");
                return -1;
            }
        } else if (!strcmp(argv[i], "--no-raw-fallback")) {
            opt->no_raw_fallback = 1;
        } else if (!strcmp(argv[i], "--segments-active-low")) {
            opt->segments_active_low = 1;
        } else if (!strcmp(argv[i], "--segments-active-high")) {
            opt->segments_active_low = 0;
        } else if (!strcmp(argv[i], "--reverse-digits")) {
            opt->reverse_digits = 1;
        } else if (!strcmp(argv[i], "--no-reverse-digits")) {
            opt->reverse_digits = 0;
        } else if (!strcmp(argv[i], "--fake") && i + 1 < argc) {
            if (parse_fake_pair(argv[++i], &opt->fake_fpga_mc, &opt->fake_ambient_mc) < 0) {
                fprintf(stderr, "invalid --fake value, expected A,B like 42.3,25.6\n");
                return -1;
            }
            opt->fake = 1;
        } else {
            fprintf(stderr, "unknown or incomplete option: %s\n", argv[i]);
            usage(argv[0]);
            return -1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    struct options opt;
    if (parse_args(argc, argv, &opt) < 0)
        return 2;

    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    struct csr_map csr;
    if (csr_open(&csr, opt.csr_device, opt.csr_base, 0x100) < 0)
        return 1;

    fprintf(stderr,
            "sevenseg_temp_display: csr=%s@0x%08lx fake=%d hwmon=%s ambient=%s@0x%02x raw_xadc=0x%08lx raw_i2c=0x%08lx raw_fallback=%d active_low=%d reverse=%d scan_hz=%u\n",
            opt.csr_device, opt.csr_base, opt.fake, opt.hwmon_name,
            opt.ambient_i2c_bus, opt.ambient_i2c_addr, opt.xadc_csr_base,
            opt.temp_i2c_csr_base, !opt.no_raw_fallback, opt.segments_active_low,
            opt.reverse_digits, opt.scan_hz);

    struct cell cells[DIGITS];
    for (int i = 0; i < DIGITS; i++) {
        cells[i].ch = '-';
        cells[i].dp = 0;
    }

    scanner_blank(&csr, &opt);
    long next_update = 0;
    while (!stop_requested) {
        long now = monotonic_ms();
        if (now >= next_update) {
            build_display_cells(&opt, cells);
            scanner_write_cells(&csr, &opt, cells);
            next_update = now + opt.update_ms;
        }
        sleep_ms(20);
    }

    scanner_blank(&csr, &opt);
    csr_close(&csr);
    return 0;
}
