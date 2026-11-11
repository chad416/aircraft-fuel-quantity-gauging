/*
 * Acquisition / output frame tests (FQ-70..FQ-73).
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"

static void sample(fq_frame_t *f)
{
	memset(f, 0, sizeof(*f));
	for (unsigned t = 0; t < FQ_NT; t++) {
		for (unsigned i = 0; i < FQ_NP; i++)
			f->caps[t][i] = 50.0f + 10.0f * (float)i + 0.37f * (float)t;
		f->comp[t] = 41.23f + (float)t;
		f->rho[t] = 801.5f + (float)t;
	}
	f->sf.fx = -0.141f;
	f->sf.fy = 0.052f;
	f->sf.fz = 0.99f;
	f->sf.valid = true;
	f->rho_valid[0] = true;
	f->low_wet[1] = true;
}

static void test_crc(void)
{
	const uint8_t s[] = "123456789";
	CHECK_EQ(fq_crc16(s, 9), 0x29B1); /* CRC-16/CCITT-FALSE check value */
}

static int feed_all(fq_parser_t *p, const uint8_t *b, uint32_t n, fq_frame_t *f)
{
	int got = 0;
	for (uint32_t i = 0; i < n; i++)
		got += fq_parser_feed(p, b[i], f) ? 1 : 0;
	return got;
}

static void test_roundtrip(void)
{
	uint8_t buf[FQ_MAX_FRAME + 4];
	fq_frame_t f, r;
	fq_parser_t p;

	sample(&f);
	CHECK_EQ(fq_acq_encode(1, &f, buf, 10), 0); /* too small */
	uint32_t n = fq_acq_encode(42, &f, buf, sizeof(buf));
	CHECK_EQ(n, FQ_MAX_FRAME);
	fq_parser_init(&p);
	memset(&r, 0, sizeof(r));
	CHECK_EQ(feed_all(&p, buf, n, &r), 1);
	CHECK_EQ(p.seq, 42);
	CHECK_EQ(p.frames, 1);
	for (unsigned t = 0; t < FQ_NT; t++) {
		for (unsigned i = 0; i < FQ_NP; i++)
			CHECK_NEAR(r.caps[t][i], f.caps[t][i], 0.006);
		CHECK_NEAR(r.comp[t], f.comp[t], 0.006);
		CHECK_NEAR(r.rho[t], f.rho[t], 0.06);
	}
	CHECK_NEAR(r.sf.fx, -0.141, 0.0011);
	CHECK_NEAR(r.sf.fy, 0.052, 0.0011);
	CHECK_NEAR(r.sf.fz, 0.99, 0.0011);
	CHECK(r.sf.valid);
	CHECK(r.rho_valid[0] && !r.rho_valid[1]);
	CHECK(!r.low_wet[0] && r.low_wet[1]);

	/* the other flag combination; sf flagged valid but fz implausible */
	f.sf.valid = false;
	f.rho_valid[0] = false;
	f.rho_valid[1] = true;
	f.low_wet[0] = true;
	f.low_wet[1] = false;
	n = fq_acq_encode(43, &f, buf, sizeof(buf));
	CHECK_EQ(feed_all(&p, buf, n, &r), 1);
	CHECK(!r.sf.valid && !r.rho_valid[0] && r.rho_valid[1] && r.low_wet[0] && !r.low_wet[1]);
	f.sf.valid = true;
	f.sf.fz = 0.05f;
	n = fq_acq_encode(44, &f, buf, sizeof(buf));
	CHECK_EQ(feed_all(&p, buf, n, &r), 1);
	CHECK(!r.sf.valid);

	/* saturation of the 16-bit fields */
	f.caps[0][0] = -5.0f;
	f.caps[0][1] = 9999.0f;
	f.sf.fx = -40.0f;
	f.sf.fy = 40.0f;
	n = fq_acq_encode(45, &f, buf, sizeof(buf));
	CHECK_EQ(feed_all(&p, buf, n, &r), 1);
	CHECK_NEAR(r.caps[0][0], 0.0, 1e-6);
	CHECK_NEAR(r.caps[0][1], 655.35, 1e-3);
	CHECK_NEAR(r.sf.fx, -32.768, 1e-3);
	CHECK_NEAR(r.sf.fy, 32.767, 1e-3);
}

static void test_parser_errors(void)
{
	uint8_t buf[FQ_MAX_FRAME + 4];
	fq_frame_t f, r;
	fq_parser_t p;
	sample(&f);
	uint32_t n = fq_acq_encode(1, &f, buf, sizeof(buf));

	/* bit flip in the payload: CRC error, then the next frame is taken */
	fq_parser_init(&p);
	buf[10] ^= 0x04;
	CHECK_EQ(feed_all(&p, buf, n, &r), 0);
	CHECK_EQ(p.crc_errors, 1);
	buf[10] ^= 0x04;
	CHECK_EQ(feed_all(&p, buf, n, &r), 1);

	/* wrong type with a valid CRC */
	uint8_t t[FQ_MAX_FRAME + 4];
	memcpy(t, buf, n);
	t[3] = FQ_T_OUT;
	uint16_t c = fq_crc16(&t[2], FQ_ACQ_LEN + 2);
	t[FQ_HDR_LEN + FQ_ACQ_LEN] = (uint8_t)(c >> 8);
	t[FQ_HDR_LEN + FQ_ACQ_LEN + 1] = (uint8_t)c;
	CHECK_EQ(feed_all(&p, t, n, &r), 0);
	CHECK_EQ(p.format_errors, 1);

	/* acquisition type with a short (valid-CRC) payload */
	uint8_t s[16] = {FQ_SYNC0, FQ_SYNC1, 4, FQ_T_ACQ, 1, 2, 3, 4};
	c = fq_crc16(&s[2], 6);
	s[8] = (uint8_t)(c >> 8);
	s[9] = (uint8_t)c;
	CHECK_EQ(feed_all(&p, s, 10, &r), 0);
	CHECK_EQ(p.format_errors, 2);

	/* oversize length byte */
	uint8_t o[] = {FQ_SYNC0, FQ_SYNC1, (uint8_t)(FQ_ACQ_LEN + 1)};
	CHECK_EQ(feed_all(&p, o, 3, &r), 0);
	CHECK_EQ(p.format_errors, 3);

	/* resynchronisation: garbage, A5 A5 5A, A5 then junk */
	uint8_t g[] = {0x00, 0x5A, FQ_SYNC0, 0x11, FQ_SYNC0, FQ_SYNC0};
	CHECK_EQ(feed_all(&p, g, sizeof(g), &r), 0);
	CHECK_EQ(feed_all(&p, &buf[1], n - 1, &r), 1);
}

static void test_out(void)
{
	fq_ctx_t x;
	uint8_t buf[64];
	fq_init(&x);
	x.status = 0x2A5;
	x.t[0].m_filt = 321.4f;
	x.t[1].res.excluded = 3;
	x.t[1].ssm = FQ_SSM_NO;
	x.total_kg = 700.0f;
	x.total_ssm = FQ_SSM_NO;
	x.words[2] = 0xDEADBEEF;
	CHECK_EQ(fq_out_encode(&x, 9, buf, 10), 0);
	uint32_t n = fq_out_encode(&x, 9, buf, sizeof(buf));
	CHECK_EQ(n, FQ_HDR_LEN + FQ_OUT_LEN + FQ_CRC_LEN);
	CHECK_EQ(buf[3], FQ_T_OUT);
	uint8_t *p = &buf[FQ_HDR_LEN];
	CHECK_EQ(p[0], 9);
	CHECK_EQ(p[1] | (p[2] << 8), 0x2A5);
	CHECK_EQ((p[5] << 8) | p[6], 3214);
	CHECK_EQ(p[3 + 9 + 8], (3 + 1) | (FQ_SSM_NO << 4));
	CHECK_EQ((p[21] << 8) | p[22], 7000);
	CHECK_EQ(p[24 + 8], 0xDE);
	CHECK_EQ(p[27 + 8], 0xEF);
	CHECK_EQ((buf[n - 2] << 8) | buf[n - 1], fq_crc16(&buf[2], FQ_OUT_LEN + 2));
}

void test_frame(void)
{
	test_crc();
	test_roundtrip();
	test_parser_errors();
	test_out();
}
