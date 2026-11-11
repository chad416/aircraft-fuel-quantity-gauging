/*
 * Single-cycle core tests (FQ-10..FQ-30): every decision of solve.c on
 * constructed states (the statistical evidence is in test_vectors.c and S4/S5).
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"

#define EPS 2.13f

static void base_in(fq_in_t *in, const float *caps)
{
	memset(in, 0, sizeof(*in));
	in->caps = caps;
	in->eps = EPS;
	in->eps_ok = true;
	in->sf.fz = 1.0f;
	in->sf.valid = true;
}

static void test_eps_density(void)
{
	float e = 0.0f;
	const fq_tank_cfg_t *c = right();
	CHECK(fq_comp_eps(c, comp_caps(c, 2.10f), &e));
	CHECK_NEAR(e, 2.10, 1e-4);
	CHECK(!fq_comp_eps(c, comp_caps(c, 1.80f), &e)); /* below the window */
	CHECK(!fq_comp_eps(c, comp_caps(c, 2.50f), &e)); /* above */
	CHECK(fq_comp_eps(c, comp_caps(c, FQ_EPS_MAX - 1e-4f), &e));
	/* Clausius-Mossotti density of the nominal fuel: about 807 kg/m^3 at eps 2.131 */
	CHECK_NEAR(fq_rho_from_eps(2.1308f), 807.5, 1.5);
}

static void test_classify(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	float h[FQ_NP];
	uint8_t cl[FQ_NP];
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	caps[0] = c->p[0].cdry - 5.0f;                              /* open */
	caps[1] = c->p[1].cdry + c->p[1].k * 1.6f * c->p[1].len + 3.0f; /* short or water */
	caps[2] = c->p[2].cdry + 0.01f;                              /* dry */
	caps[3] = c->p[3].cdry + c->p[3].k * (EPS - 1.0f) * c->p[3].len; /* full */
	fq_classify(c, caps, EPS, h, cl);
	CHECK_EQ(cl[0], FQ_CL_OPEN);
	CHECK_EQ(cl[1], FQ_CL_SHORT);
	CHECK_EQ(cl[2], FQ_CL_DRY);
	CHECK_EQ(cl[3], FQ_CL_FULL);
	CHECK_EQ(cl[4], FQ_CL_LIVE);
	CHECK_NEAR(h[4], 0.05f - c->p[4].zbot, 1e-5);
	CHECK(fq_weight(0.0f) > fq_weight(0.3f));
}

static void test_fit(void)
{
	const fq_tank_cfg_t *c = right();
	float zs[FQ_NP];
	float w[FQ_NP];
	fq_plane_t pl;
	for (unsigned i = 0; i < FQ_NP; i++) {
		zs[i] = 0.02f + 0.1f * (c->p[i].x - c->xr) - 0.05f * (c->p[i].y - c->yr);
		w[i] = fq_weight(0.1f);
	}
	CHECK(fq_fit_plane(c, 0xFF, zs, w, &pl));
	CHECK_NEAR(pl.z_ref, 0.02, 1e-5);
	CHECK_NEAR(pl.sx, 0.1, 1e-4);
	CHECK_NEAR(pl.sy, -0.05, 1e-4);
	CHECK(pl.chi2 < 1e-3);
	CHECK(!fq_fit_plane(c, 0x03, zs, w, &pl)); /* two probes */
	CHECK(!fq_fit_plane(c, 0x07, zs, w, &pl)); /* three probes on one rib: collinear */
}

static void test_table(void)
{
	CHECK(fq_in_table(0.0f, 0.0f));
	CHECK(!fq_in_table(FQ_SX_MIN - 0.01f, 0.0f));
	CHECK(!fq_in_table(FQ_SX_MAX + 0.01f, 0.0f));
	CHECK(!fq_in_table(0.0f, FQ_SY_MIN - 0.01f));
	CHECK(!fq_in_table(0.0f, FQ_SY_MAX + 0.01f));
	/* empty below the bottom, full above the top, monotonic between */
	CHECK_NEAR(fq_table_volume(-5.0f, 0.0f, 0.0f), 0.0, 1e-6);
	const float vfull = fq_table_volume(5.0f, 0.0f, 0.0f);
	CHECK(vfull > 0.85f && vfull < 1.0f);
	CHECK_NEAR(fq_table_volume(5.0f, FQ_SX_MAX, FQ_SY_MAX), vfull, 1e-4); /* table corner */
	float last = -1.0f;
	int mono = 1;
	for (int k = 0; k <= 50; k++) {
		float v = fq_table_volume(-0.2f + 0.01f * (float)k, 0.05f, 0.02f);
		mono &= v >= last;
		last = v;
	}
	CHECK(mono);
}

static void test_sf(void)
{
	fq_sf_t sf = {-0.1f, 0.05f, 1.0f, true};
	float sx;
	float sy;
	fq_sf_slopes(right(), &sf, &sx, &sy);
	CHECK_NEAR(sx, 0.1, 1e-6);
	CHECK_NEAR(sy, -0.05, 1e-6);
	fq_sf_slopes(left(), &sf, &sx, &sy);
	CHECK_NEAR(sy, 0.05, 1e-6);
}

static void test_solve_nominal(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	fq_in_t in;
	fq_res_t r;
	plane_caps(c, 0.05f, 0.06f, -0.03f, EPS, caps);
	base_in(&in, caps);
	in.sf.fx = -0.06f;
	in.sf.fy = 0.03f;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.status, FQ_ST_OK);
	CHECK(r.verified && !r.detected && !r.fallback);
	CHECK_EQ(r.n_live, 8);
	CHECK_NEAR(r.z_ref, 0.05, 1e-4);
	CHECK_NEAR(r.sx, 0.06, 1e-3);
	CHECK_NEAR(r.mass, r.usable * fq_rho_from_eps(EPS), 1e-3);
	/* densitometer and a substitute eps */
	in.rho_valid = true;
	in.rho_meas = 790.0f;
	in.eps_ok = false;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.status, FQ_ST_DEGRADED);
	CHECK_NEAR(r.rho, 790.0, 1e-4);
	/* a latched failed probe is excluded and the fit still verified */
	in.failed = 0x10;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.cl[4], FQ_CL_EXCL);
	CHECK_EQ(r.n_live, 7);
	/* almost empty: below the unusable volume the usable volume is zero */
	plane_caps(c, -0.170f, 0.0f, 0.0f, EPS, caps);
	in.failed = 0;
	fq_solve(c, &in, &r);
	CHECK_NEAR(r.usable, 0.0, 1e-9);
}

static void test_solve_exclusion(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	fq_in_t in;
	fq_res_t r;
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	base_in(&in, caps);
	/* one probe 40 mm high: detected and excluded */
	caps[5] += c->p[5].k * (EPS - 1.0f) * 0.040f;
	fq_solve(c, &in, &r);
	CHECK(r.detected);
	CHECK_EQ(r.excluded, 5);
	CHECK_EQ(r.cl[5], FQ_CL_EXCL);
	CHECK_NEAR(r.z_ref, 0.05, 1e-3);
	/* two probes wrong in opposite directions: detected, not isolated -> invalid */
	caps[1] -= c->p[1].k * (EPS - 1.0f) * 0.050f;
	fq_solve(c, &in, &r);
	CHECK(r.detected);
	CHECK_EQ(r.status, FQ_ST_INVALID);
	/* four LIVE probes: detection only -> invalid */
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	caps[3] += c->p[3].k * (EPS - 1.0f) * 0.100f;
	in.failed = 0x56; /* leaves probes 0, 3, 5, 7: a well-spread set of four */
	fq_solve(c, &in, &r);
	CHECK_EQ(r.n_live, 4);
	CHECK(r.detected);
	CHECK_EQ(r.status, FQ_ST_INVALID);
}

static void test_solve_degenerate_subset(void)
{
	/* four probes on one rib plus one elsewhere: leaving the fifth out is collinear */
	fq_tank_cfg_t c = *right();
	float caps[FQ_NP];
	fq_in_t in;
	fq_res_t r;
	c.p[3].y = c.p[0].y;
	c.p[3].x = 0.6f;
	plane_caps(&c, 0.05f, 0.0f, 0.0f, EPS, caps);
	caps[1] += c.p[1].k * (EPS - 1.0f) * 0.060f;
	base_in(&in, caps);
	in.failed = 0xE0;
	fq_solve(&c, &in, &r);
	CHECK(r.detected);
	CHECK_EQ(r.excluded, 1);
	CHECK_EQ(r.n_live, 4);
	CHECK_EQ(r.status, FQ_ST_OK);
}

static void test_solve_saturated(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	fq_in_t in;
	fq_res_t r;
	/* verified plane; a DRY-reading probe that must be wet, and a FULL one that must be dry */
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	base_in(&in, caps);
	caps[6] = c->p[6].cdry;
	caps[7] = c->p[7].cdry + c->p[7].k * (EPS - 1.0f) * c->p[7].len;
	fq_solve(c, &in, &r);
	CHECK(r.verified);
	CHECK_EQ(r.sat_bad, 0xC0);
	CHECK_EQ(r.status, FQ_ST_OK);
	/* consistent saturated probes: high fill, the root probes FULL */
	float z = z_for_probe(c, 5, 0.6f, 0.0f, 0.0f);
	plane_caps(c, z, 0.0f, 0.0f, EPS, caps);
	fq_solve(c, &in, &r);
	CHECK_EQ(r.sat_bad, 0);
	/* an unverified plane (3 LIVE) contradicted by a FULL probe: fallback to the specific force */
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	in.failed = 0x1A; /* leaves probes 0, 2, 5, 6, 7: make 5 and 6 FULL-reading */
	caps[5] = c->p[5].cdry + c->p[5].k * (EPS - 1.0f) * c->p[5].len;
	caps[6] = c->p[6].cdry + c->p[6].k * (EPS - 1.0f) * c->p[6].len;
	fq_solve(c, &in, &r);
	CHECK(r.fallback);
	CHECK_EQ(r.status, FQ_ST_DEGRADED);
	CHECK_EQ(r.sat_bad, 0);
}

static void test_solve_fallback(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	fq_in_t in;
	fq_res_t r;
	plane_caps(c, 0.05f, 0.05f, 0.0f, EPS, caps);
	base_in(&in, caps);
	in.sf.fx = -0.05f;
	in.failed = 0xFC; /* two LIVE probes left */
	fq_solve(c, &in, &r);
	CHECK(r.fallback);
	CHECK_EQ(r.status, FQ_ST_DEGRADED);
	CHECK_NEAR(r.z_ref, 0.05, 1e-4);
	/* no specific force: the held slopes */
	in.sf.valid = false;
	in.hold_valid = true;
	in.hold_sx = 0.05f;
	fq_solve(c, &in, &r);
	CHECK(r.fallback);
	CHECK_NEAR(r.z_ref, 0.05, 1e-4);
	/* neither: invalid */
	in.hold_valid = false;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.status, FQ_ST_INVALID);
	/* every probe failed: invalid */
	in.sf.valid = true;
	in.failed = 0xFF;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.status, FQ_ST_INVALID);
	/* all DRY: empty */
	in.sf.fx = 0.0f;
	plane_caps(c, -1.0f, 0.0f, 0.0f, EPS, caps);
	in.failed = 0;
	fq_solve(c, &in, &r);
	CHECK(r.fallback);
	CHECK_NEAR(r.volume, 0.0, 1e-6);
	/* all FULL: the lowest plane that covers every probe top (indicated <= true) */
	plane_caps(c, 1.0f, 0.0f, 0.0f, EPS, caps);
	fq_solve(c, &in, &r);
	CHECK(r.fallback);
	float top = -1.0f;
	for (unsigned i = 0; i < FQ_NP; i++) {
		float t = c->p[i].zbot + c->p[i].len;
		if (t > top)
			top = t;
	}
	CHECK_NEAR(r.z_ref, top, 1e-5);
	CHECK(r.volume < fq_table_volume(1.0f, 0.0f, 0.0f));
	/* slopes outside the table: invalid */
	plane_caps(c, 0.05f, 0.0f, 0.0f, EPS, caps);
	in.failed = 0xFC;
	in.sf.fx = -0.6f;
	fq_solve(c, &in, &r);
	CHECK_EQ(r.status, FQ_ST_INVALID);
}

static void test_monitor(void)
{
	const fq_tank_cfg_t *c = right();
	float caps[FQ_NP];
	float v = 0.0f;
	fq_sf_t sf = {-0.04f, 0.0f, 1.0f, true};
	plane_caps(c, 0.05f, 0.04f, 0.0f, EPS, caps);
	CHECK(fq_monitor(c, caps, EPS, &sf, 0, &v)); /* 8 LIVE: even count */
	const float v8 = v;
	CHECK(fq_monitor(c, caps, EPS, &sf, 0x01, &v)); /* 7: odd count */
	CHECK_NEAR(v, v8, 2e-3);
	fq_in_t in;
	fq_res_t r;
	base_in(&in, caps);
	in.sf = sf;
	fq_solve(c, &in, &r);
	CHECK_NEAR(v8, r.usable, 2e-3);
	/* unavailable: no specific force, outside the table, no LIVE probe */
	sf.valid = false;
	CHECK(!fq_monitor(c, caps, EPS, &sf, 0, &v));
	sf.valid = true;
	sf.fx = -0.6f;
	CHECK(!fq_monitor(c, caps, EPS, &sf, 0, &v));
	sf.fx = 0.0f;
	CHECK(!fq_monitor(c, caps, EPS, &sf, 0xFF, &v));
	/* empty tank: usable clamps at zero */
	plane_caps(c, -0.150f, 0.0f, 0.0f, EPS, caps);
	if (fq_monitor(c, caps, EPS, &sf, 0, &v)) {
		CHECK(v >= 0.0f);
	}
}

void test_solve(void)
{
	test_eps_density();
	test_classify();
	test_fit();
	test_table();
	test_sf();
	test_solve_nominal();
	test_solve_exclusion();
	test_solve_degenerate_subset();
	test_solve_saturated();
	test_solve_fallback();
	test_monitor();
}
