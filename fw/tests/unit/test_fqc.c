/*
 * Gauge computer tests (FQ-40..FQ-58): persistence and latching, permittivity
 * selection and cross-check, filter, invalid handling, COM/MON, low fuel,
 * FQ DISAGREE, no data, sign/status matrix and output words.
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"

#define EPS 2.13f
#define ZL 0.05f
#define ZR 0.04f

static void run(fq_ctx_t *x, const fq_frame_t *f, int n)
{
	for (int i = 0; i < n; i++)
		fq_step(x, f);
}

static void test_nominal(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	fq_init(&x);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NCD);
	frame_for(&f, ZL, ZR, 0.03f, 0.01f, EPS);
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NO);
	CHECK_EQ(x.t[1].ssm, FQ_SSM_NO);
	CHECK_EQ(x.total_ssm, FQ_SSM_NO);
	CHECK_NEAR(x.t[1].m_filt, x.t[1].res.mass, 1e-4); /* first value taken as is */
	CHECK_NEAR(x.total_kg, x.t[0].m_filt + x.t[1].m_filt, 1e-3);
	CHECK(x.t[0].hold_valid);
	CHECK_EQ(x.status, 0u);
	for (int i = 0; i < 4; i++)
		CHECK_EQ(fq_a429_parity_ok(x.words[i]), 1u);
	CHECK_NEAR(fq_a429_bnr_value(x.words[2], FQ_A429_RANGE_KG), x.total_kg, 0.02);
	CHECK_EQ((x.words[2] >> 29) & 3u, FQ_SSM_NO);
	/* filter: a step in the right tank moves the indication by alpha per cycle */
	const float m0 = x.t[1].m_filt;
	frame_for(&f, ZL, ZR + 0.02f, 0.03f, 0.01f, EPS);
	fq_step(&x, &f);
	CHECK_NEAR(x.t[1].m_filt, m0 + FQ_FILT_ALPHA * (x.t[1].res.mass - m0), 1e-3);
	/* the two tanks see the same fuel plane in their own frames: equal z, equal mass */
	frame_for(&f, ZR, ZR, 0.03f, 0.0f, EPS);
	fq_init(&x);
	fq_step(&x, &f);
	CHECK_NEAR(x.t[0].m_filt, x.t[1].m_filt, 0.05);
}

static void test_persistence(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	/* a two-cycle glitch is not latched */
	f.caps[1][3] = 0.2f;
	run(&x, &f, 2);
	CHECK_EQ(x.t[1].failed, 0);
	CHECK_EQ(x.t[1].cnt[3], 2);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].cnt[3], 0);
	/* three cycles: latched, and it stays latched when the reading comes back */
	f.caps[1][3] = 0.2f;
	run(&x, &f, 3);
	CHECK_EQ(x.t[1].failed, 0x08);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	run(&x, &f, 5);
	CHECK_EQ(x.t[1].failed, 0x08);
	CHECK(x.status & FQ_ST_DEG_R);
	CHECK_EQ(x.t[1].ssm, FQ_SSM_NO);
	/* a short (or water) and a DRY probe the verified plane says is wet: both latched */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.caps[1][1] = 900.0f;
	f.caps[1][6] = right()->p[6].cdry;
	run(&x, &f, 3);
	CHECK_EQ(x.t[1].failed, 0x08 | 0x02 | 0x40);
	/* an in-range bias: excluded each cycle, latched after three */
	const fq_tank_cfg_t *c = left();
	f.caps[0][5] += c->p[5].k * (EPS - 1.0f) * 0.04f;
	run(&x, &f, 3);
	CHECK_EQ(x.t[0].failed, 0x20);
}

static void test_eps_selection(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	/* never a plausible compensator: default eps, degraded */
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.comp[0] = 0.0f;
	f.comp[1] = 0.0f;
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].res.status, FQ_ST_DEGRADED);
	CHECK(!x.t[0].eps_valid);
	/* both plausible and equal: own */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, 2.10f);
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].res.status, FQ_ST_OK);
	CHECK_NEAR(x.t[1].eps_last, 2.10, 1e-4);
	/* right implausible: the left one is used */
	f.comp[1] = 0.0f;
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].res.status, FQ_ST_DEGRADED);
	CHECK_EQ(x.t[0].res.status, FQ_ST_OK);
	/* both implausible: last good */
	f.comp[0] = 0.0f;
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].res.status, FQ_ST_DEGRADED);
	CHECK_NEAR(x.t[0].res.rho, fq_rho_from_eps(2.10f), 1e-3);
	/* cross-check: 2.10 against 2.16 -> both use 2.16 (lower mass), XCOMP */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, 2.10f);
	f.comp[1] = comp_caps(right(), 2.16f);
	fq_step(&x, &f);
	CHECK(x.xcomp);
	CHECK(x.status & FQ_ST_XCOMP);
	CHECK_NEAR(x.t[0].res.rho, fq_rho_from_eps(2.16f), 1e-3);
	CHECK_EQ(x.t[0].res.status, FQ_ST_DEGRADED);
	/* ... and the larger may be on either side */
	f.comp[0] = comp_caps(left(), 2.17f);
	f.comp[1] = comp_caps(right(), 2.10f);
	fq_step(&x, &f);
	CHECK_NEAR(x.t[1].res.rho, fq_rho_from_eps(2.17f), 1e-3);
}

static void test_invalid(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	const float held = x.t[1].m_filt;
	for (unsigned i = 0; i < FQ_NP; i++)
		f.caps[1][i] = 0.1f; /* every probe open */
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].ssm, FQ_SSM_NCD);
	CHECK_EQ(x.total_ssm, FQ_SSM_NCD);
	CHECK(x.status & FQ_ST_FAIL_R);
	CHECK_NEAR(x.t[1].m_filt, held, 1e-6);
	CHECK(x.t[1].m_valid);
	run(&x, &f, (int)FQ_INVALID_N);
	CHECK(!x.t[1].m_valid);
	/* back: re-initialised (the probes are latched failed now: fallback, degraded) */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_init(&x);
	fq_step(&x, &f);
	CHECK(x.t[1].m_valid);
}

static void test_monitor_fail(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	fq_init(&x);
	/* the specific force says 9 deg nose-up while the fuel is level (AHRS wrong):
	 * MON disagrees with COM by more than its limit */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.sf.fx = -0.16f;
	fq_step(&x, &f);
	CHECK(x.t[1].mon_ok);
	CHECK(fabsf(x.t[1].mon_kg - x.t[1].res.mass) > right()->mon_tol_kg);
	run(&x, &f, (int)FQ_MON_N - 2);
	CHECK(!x.t[1].mon_fail);
	fq_step(&x, &f);
	CHECK(x.t[1].mon_fail);
	CHECK_EQ(x.t[1].ssm, FQ_SSM_FW);
	CHECK_EQ(x.total_ssm, FQ_SSM_FW);
	CHECK_EQ((x.words[1] >> 29) & 3u, FQ_SSM_FW);
	/* a disagreement that clears resets the count */
	fq_init(&x);
	run(&x, &f, 5);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].mon_cnt, 0);
	/* no data keeps a failure warning */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.sf.fx = -0.16f;
	fq_init(&x);
	run(&x, &f, (int)FQ_MON_N);
	for (unsigned i = 0; i < FQ_NODATA_N; i++)
		fq_no_data(&x);
	CHECK_EQ(x.t[1].ssm, FQ_SSM_FW);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_FW); /* the wrong specific force fails both tanks' MON */
	/* a failure warning on the left only */
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.sf.fx = -0.16f;
	f.sf.fy = 0.0f;
	run(&x, &f, (int)FQ_MON_N);
	x.t[0].mon_fail = false; /* keep the right tank's failure warning only */
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NO);
	CHECK_EQ(x.total_ssm, FQ_SSM_FW);
	/* COM invalid (detected, not isolated) while MON computes: no comparison */
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	x.t[1].failed = 0x56;
	f.caps[1][3] += right()->p[3].k * (EPS - 1.0f) * 0.100f;
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].res.status, FQ_ST_INVALID);
	CHECK(x.t[1].mon_ok);
	CHECK_EQ(x.t[1].mon_cnt, 0);
}

static void test_no_data(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	for (unsigned i = 0; i + 1 < FQ_NODATA_N; i++)
		fq_no_data(&x);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NO);
	fq_no_data(&x);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NCD);
	CHECK(x.status & FQ_ST_NODATA);
	fq_step(&x, &f);
	CHECK_EQ(x.t[0].ssm, FQ_SSM_NO);
	CHECK_EQ(x.nodata, 0);
	x.nodata = 0xFFFF;
	fq_no_data(&x);
	CHECK_EQ(x.nodata, 0xFFFF);
}

static void test_low_fuel(void)
{
	fq_ctx_t x;
	fq_frame_t f;
	/* the sensor goes dry: warning after FQ_LOW_N cycles */
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	f.low_wet[0] = false;
	run(&x, &f, (int)FQ_LOW_N - 1);
	CHECK(!x.t[0].low_warn);
	fq_step(&x, &f);
	CHECK(x.t[0].low_warn);
	CHECK(x.status & FQ_ST_LOW_L);
	CHECK(!(x.status & FQ_ST_LOW_R));
	/* dry for 60 s while the gauge reads high: FQ DISAGREE */
	run(&x, &f, (int)(FQ_DIS_N - FQ_LOW_N));
	CHECK(x.t[0].disagree);
	CHECK(x.status & FQ_ST_DIS_L);
	/* wet again: both clear */
	f.low_wet[0] = true;
	fq_step(&x, &f);
	CHECK(!x.t[0].low_warn && !x.t[0].disagree);
	/* the gauge alone below the threshold */
	fq_init(&x);
	frame_for(&f, -0.135f, -0.135f, 0.0f, 0.0f, EPS);
	fq_step(&x, &f);
	CHECK(x.t[1].m_filt < FQ_LOW_KG);
	run(&x, &f, (int)FQ_LOW_N);
	CHECK(x.t[1].low_warn);
	CHECK(x.status & FQ_ST_LOW_R);
	/* the sensor dry and the gauge low agree: no FQ DISAGREE */
	f.low_wet[1] = false;
	run(&x, &f, (int)FQ_DIS_N);
	CHECK(!x.t[1].disagree);
	/* the sensor dry for 60 s while the gauge has no computed data: no FQ DISAGREE */
	fq_init(&x);
	frame_for(&f, ZL, ZR, 0.0f, 0.0f, EPS);
	for (unsigned i = 0; i < FQ_NP; i++)
		f.caps[1][i] = 0.1f;
	f.low_wet[1] = false;
	run(&x, &f, (int)FQ_DIS_N);
	CHECK(x.t[1].low_warn && !x.t[1].disagree);
	/* counter saturation */
	x.t[1].low_cnt = 0xFFFF;
	fq_step(&x, &f);
	CHECK_EQ(x.t[1].low_cnt, 0xFFFF);
}

void test_fqc(void)
{
	test_nominal();
	test_persistence();
	test_eps_selection();
	test_invalid();
	test_monitor_fail();
	test_no_data();
	test_low_fuel();
}
