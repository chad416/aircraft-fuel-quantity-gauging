/*
 * Fuel quantity gauge computer: Zephyr glue around lib/fq.
 *
 *  - bus UART (LPUART3; RS-422 to the probe-transmitter concentrator on a real
 *    unit): RX ISR -> ring -> frame parser
 *  - computation thread, one cycle every 100 ms (k_timer): the newest
 *    acquisition frame -> fq_step, or fq_no_data if none arrived; the output
 *    frame with the four ARINC 429 words goes back on the same UART (on a real
 *    unit the words go to an ARINC 429 transmitter, e.g. over SPI)
 *  - LOW FUEL lamp discrete on GPIO1_IO09
 *
 * SPDX-License-Identifier: MIT
 */
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/ring_buffer.h>

#include "fq/fq.h"

#define USER_NODE DT_PATH(zephyr_user)
static const struct gpio_dt_spec lamp = GPIO_DT_SPEC_GET(USER_NODE, lamp_gpios);
static const struct device *const bus_uart = DEVICE_DT_GET(DT_CHOSEN(fq_bus_uart));

static fq_ctx_t ctx;
static fq_parser_t parser;
static fq_frame_t frame;

/* ---- Diagnostics, read by the test rig through the ELF symbols ------------ */

volatile uint32_t fq_diag_cycles;
volatile uint32_t fq_diag_max_cyc; /* worst fq_step time, CPU cycles */
volatile uint32_t fq_diag_rx_overflow;
volatile uint32_t fq_diag_lamp;
#ifdef CONFIG_FQ_TEST_HOOKS
volatile uint32_t fq_diag_frames;
volatile uint32_t fq_diag_crc_errors;
#endif

/* ---- Bus receive ------------------------------------------------------------ */

RING_BUF_DECLARE(rx_ring, 1024);

static void uart_isr(const struct device *dev, void *user)
{
	ARG_UNUSED(user);
	uart_irq_update(dev);
	while (uart_irq_rx_ready(dev)) {
		uint8_t buf[32];
		const int n = uart_fifo_read(dev, buf, sizeof(buf));

		if (n <= 0) {
			break;
		}
		if (ring_buf_put(&rx_ring, buf, (uint32_t)n) < (uint32_t)n) {
			fq_diag_rx_overflow++;
		}
	}
}

/* ---- Computation thread ----------------------------------------------------- */

static K_SEM_DEFINE(tick_sem, 0, 1);

static void tick(struct k_timer *t)
{
	ARG_UNUSED(t);
	k_sem_give(&tick_sem);
}

static K_TIMER_DEFINE(tick_timer, tick, NULL);

static void gauge_thread(void *a, void *b, void *c)
{
	static uint8_t out[FQ_HDR_LEN + FQ_OUT_LEN + FQ_CRC_LEN];
	uint8_t rx[64];
	uint8_t seq = 0U;

	ARG_UNUSED(a);
	ARG_UNUSED(b);
	ARG_UNUSED(c);
	k_timer_start(&tick_timer, K_MSEC(100), K_MSEC(100));
	for (;;) {
		uint32_t n;
		bool fresh = false;

		k_sem_take(&tick_sem, K_FOREVER);
		while ((n = ring_buf_get(&rx_ring, rx, sizeof(rx))) > 0U) {
			for (uint32_t i = 0U; i < n; i++) {
				if (fq_parser_feed(&parser, rx[i], &frame)) {
					fresh = true;
				}
			}
		}
		const uint32_t t0 = k_cycle_get_32();

		if (fresh) {
			fq_step(&ctx, &frame);
		} else {
			fq_no_data(&ctx);
		}
		const uint32_t dt = k_cycle_get_32() - t0;

		if (dt > fq_diag_max_cyc) {
			fq_diag_max_cyc = dt;
		}
		fq_diag_lamp = (ctx.t[0].low_warn || ctx.t[1].low_warn) ? 1U : 0U;
		(void)gpio_pin_set_dt(&lamp, (int)fq_diag_lamp);
		const uint32_t len = fq_out_encode(&ctx, seq, out, sizeof(out));

		for (uint32_t i = 0U; i < len; i++) {
			uart_poll_out(bus_uart, out[i]);
		}
		seq++;
		fq_diag_cycles++;
#ifdef CONFIG_FQ_TEST_HOOKS
		fq_diag_frames = parser.frames;
		fq_diag_crc_errors = parser.crc_errors;
#endif
	}
}

K_THREAD_STACK_DEFINE(gauge_stack, 8192);
static struct k_thread gauge_data;

int main(void)
{
	int err = gpio_pin_configure_dt(&lamp, GPIO_OUTPUT_INACTIVE);

	if ((err != 0) || !device_is_ready(bus_uart)) {
		printk("fq: I/O init failed (%d)\n", err);
		return 0;
	}
	fq_init(&ctx);
	fq_parser_init(&parser);
	memset(&frame, 0, sizeof(frame));
	uart_irq_callback_user_data_set(bus_uart, uart_isr, NULL);
	uart_irq_rx_enable(bus_uart);
	k_thread_create(&gauge_data, gauge_stack, K_THREAD_STACK_SIZEOF(gauge_stack), gauge_thread, NULL, NULL,
			NULL, 2, 0, K_NO_WAIT);
	k_thread_name_set(&gauge_data, "gauge");
	printk("fq READY\n");
	return 0;
}
