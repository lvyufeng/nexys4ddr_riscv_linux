#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static void msleep(long ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
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

int main(int argc, char **argv) {
    if (argc < 4 || argc > 5) {
        fprintf(stderr, "usage: %s /dev/gpiochipN lines mask [hold_ms]\n", argv[0]);
        fprintf(stderr, "example: %s /dev/gpiochip3 6 0x3f 1000\n", argv[0]);
        return 2;
    }

    const char *chip = argv[1];
    unsigned int lines = 0, mask = 0;
    if (parse_u32(argv[2], &lines) < 0 || lines == 0 || lines > GPIOHANDLES_MAX) {
        fprintf(stderr, "invalid line count: %s\n", argv[2]);
        return 2;
    }
    if (parse_u32(argv[3], &mask) < 0) {
        fprintf(stderr, "invalid mask: %s\n", argv[3]);
        return 2;
    }
    long hold_ms = 250;
    if (argc == 5)
        hold_ms = strtol(argv[4], NULL, 0);

    int fd = open(chip, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        printf("OPEN_FAIL path=%s errno=%d\n", chip, errno);
        return 1;
    }

    struct gpiochip_info info;
    memset(&info, 0, sizeof(info));
    if (ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, &info) < 0) {
        printf("CHIPINFO_FAIL path=%s errno=%d\n", chip, errno);
        close(fd);
        return 1;
    }
    printf("GPIO_CHIP path=%s name=%s label=%s lines=%u\n", chip, info.name, info.label, info.lines);
    if (info.lines < lines) {
        printf("LINE_COUNT_FAIL path=%s requested=%u actual=%u\n", chip, lines, info.lines);
        close(fd);
        return 1;
    }

    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.flags = GPIOHANDLE_REQUEST_OUTPUT;
    req.lines = lines;
    snprintf(req.consumer_label, sizeof(req.consumer_label), "gpio_output_set");
    for (unsigned int i = 0; i < lines; i++) {
        req.lineoffsets[i] = i;
        req.default_values[i] = (mask >> i) & 1u;
    }
    if (ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req) < 0) {
        printf("LINEHANDLE_FAIL path=%s errno=%d\n", chip, errno);
        close(fd);
        return 1;
    }

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));
    for (unsigned int i = 0; i < lines; i++)
        data.values[i] = (mask >> i) & 1u;
    if (ioctl(req.fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data) < 0) {
        printf("SET_VALUES_FAIL path=%s errno=%d\n", chip, errno);
        close(req.fd);
        close(fd);
        return 1;
    }

    printf("GPIO_OUTPUT_SET path=%s lines=%u mask=0x%x hold_ms=%ld\n", chip, lines, mask, hold_ms);
    fflush(stdout);
    if (hold_ms > 0)
        msleep(hold_ms);

    close(req.fd);
    close(fd);
    printf("GPIO_OUTPUT_SET_OK\n");
    return 0;
}
