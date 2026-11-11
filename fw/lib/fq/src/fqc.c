/*
 * Gauge computer, one 100 ms cycle (FQ-40..FQ-58): permittivity selection with
 * the left/right compensator cross-check, fault persistence and latching,
 * last verified slopes, indicated-mass filter, COM/MON comparison, low-fuel
 * warning and FQ DISAGREE from the independent low-level sensor, sign/status
 * matrix and the four ARINC 429 output words.
 * SPDX-License-Identifier: MIT
 */
#include "fq/fq.h"

static float absf(float v)
{
	return (v < 0.0f) ? -v : v;
}

static uint16_t inc16(uint16_t v)
{
	return (v < 0xFFFFU) ? (uint16_t)(v + 1U) : v;
}

void fq_init(fq_ctx_t *x)
{
	uint32_t t;
	uint32_t i;

	for (t = 0U; t < FQ_NT; t++) {
		fq_tank_t *k = &x->t[t];

		k->failed = 0U;
		for (i = 0U; i < FQ_NP; i++) {
			k->cnt[i] = 0U;
		}
		k->hold_valid = false;
		k->hold_sx = 0.0f;
		k->hold_sy = 0.0f;
		k->eps_valid = false;
		k->eps_last = FQ_EPS_DEFAULT;
		k->m_valid = false;
		k->m_filt = 0.0f;
		k->inv_cnt = 0U;
		k->mon_cnt = 0U;
		k->mon_fail = false;
		k->mon_kg = 0.0f;
		k->mon_ok = false;
		k->low_cnt = 0U;
		k->lowc_cnt = 0U;
		k->low_warn = false;
		k->disagree = false;
		k->ssm = FQ_SSM_NCD;
		k->res.status = FQ_ST_INVALID;
		k->res.excluded = -1;
		k->res.rho = 0.0f;
		k->res.mass = 0.0f;
	}
	x->cycles = 0U;
	x->nodata = 0U;
	x->xcomp = false;
	x->status = 0U;
	x->total_ssm = FQ_SSM_NCD;
	x->total_kg = 0.0f;
	x->words[0] = 0U;
	x->words[1] = 0U;
	x->words[2] = 0U;
	x->words[3] = 0U;
}

/* Probe fault persistence (FQ-42): a range fault, an exclusion or a DRY/FULL
 * contradiction must persist FQ_N_LATCH cycles; then the probe stays failed
 * until power-down. */
static void persist(fq_tank_t *k)
{
	uint32_t i;

	for (i = 0U; i < FQ_NP; i++) {
		const uint8_t bit = (uint8_t)(1U << i);
		const uint8_t c = k->res.cl[i];
		const bool suspect = (c == FQ_CL_OPEN) || (c == FQ_CL_SHORT) || (k->res.excluded == (int8_t)i) ||
				     ((k->res.sat_bad & bit) != 0U);

		if ((k->failed & bit) == 0U) {
			if (suspect) {
				k->cnt[i]++;
				if (k->cnt[i] >= FQ_N_LATCH) {
					k->failed = (uint8_t)(k->failed | bit);
				}
			} else {
				k->cnt[i] = 0U;
			}
		}
	}
}

static void select_eps(fq_ctx_t *x, const fq_frame_t *f, float *eps, bool *eps_ok)
{
	float e[FQ_NT] = {0.0f, 0.0f};
	bool ok[FQ_NT];
	uint32_t t;

	for (t = 0U; t < FQ_NT; t++) {
		ok[t] = fq_comp_eps(&fq_tank_cfg[t], f->comp[t], &e[t]);
	}
	/* FQ-41: both plausible but different by more than FQ_EPS_XTOL: one drifted,
	 * and which one is not known; use the larger eps (the lower mass) in both */
	x->xcomp = ok[0] && ok[1] && (absf(e[0] - e[1]) > FQ_EPS_XTOL);
	for (t = 0U; t < FQ_NT; t++) {
		fq_tank_t *k = &x->t[t];
		const uint32_t o = 1U - t;

		if (x->xcomp) {
			eps[t] = (e[0] > e[1]) ? e[0] : e[1];
			eps_ok[t] = false;
		} else if (ok[t]) {
			eps[t] = e[t];
			eps_ok[t] = true;
			k->eps_valid = true;
			k->eps_last = e[t];
		} else if (ok[o]) {
			eps[t] = e[o];
			eps_ok[t] = false;
		} else if (k->eps_valid) {
			eps[t] = k->eps_last;
			eps_ok[t] = false;
		} else {
			eps[t] = FQ_EPS_DEFAULT;
			eps_ok[t] = false;
		}
	}
}

static void low_fuel(fq_tank_t *k, bool wet)
{
	const bool computed_valid = (k->ssm == FQ_SSM_NO);

	k->low_cnt = wet ? 0U : inc16(k->low_cnt);
	k->lowc_cnt = (computed_valid && (k->m_filt < FQ_LOW_KG)) ? inc16(k->lowc_cnt) : 0U;
	/* FQ-50: either the independent sensor or the gauge, each with its own persistence */
	k->low_warn = (k->low_cnt >= FQ_LOW_N) || (k->lowc_cnt >= FQ_LOW_N);
	/* FQ-51: the sensor has been dry for 60 s but the gauge still reads well above the threshold */
	k->disagree = (k->low_cnt >= FQ_DIS_N) && computed_valid && (k->m_filt > (FQ_LOW_KG + FQ_DIS_KG));
}

static void tank_step(fq_ctx_t *x, uint32_t t, const fq_frame_t *f, float eps, bool eps_ok)
{
	const fq_tank_cfg_t *c = &fq_tank_cfg[t];
	fq_tank_t *k = &x->t[t];
	fq_in_t in;
	float vmon = 0.0f;

	in.caps = f->caps[t];
	in.eps = eps;
	in.eps_ok = eps_ok;
	in.sf = f->sf;
	in.rho_valid = f->rho_valid[t];
	in.rho_meas = f->rho[t];
	in.failed = k->failed;
	in.hold_valid = k->hold_valid;
	in.hold_sx = k->hold_sx;
	in.hold_sy = k->hold_sy;
	fq_solve(c, &in, &k->res);
	persist(k);
	if (k->res.verified) {
		k->hold_valid = true;
		k->hold_sx = k->res.sx;
		k->hold_sy = k->res.sy;
	}
	/* FQ-44: indicated-mass filter; held while invalid, dropped after FQ_INVALID_N */
	if (k->res.status != FQ_ST_INVALID) {
		k->inv_cnt = 0U;
		if (k->m_valid) {
			k->m_filt += FQ_FILT_ALPHA * (k->res.mass - k->m_filt);
		} else {
			k->m_filt = k->res.mass;
			k->m_valid = true;
		}
	} else {
		k->inv_cnt = inc16(k->inv_cnt);
		if (k->inv_cnt >= FQ_INVALID_N) {
			k->m_valid = false;
		}
	}
	/* FQ-30, FQ-45: COM/MON comparison (only when both lanes compute) */
	k->mon_ok = fq_monitor(c, f->caps[t], eps, &f->sf, k->failed, &vmon);
	if (k->mon_ok && (k->res.status != FQ_ST_INVALID)) {
		k->mon_kg = vmon * k->res.rho;
		if (absf(k->mon_kg - k->res.mass) > c->mon_tol_kg) {
			k->mon_cnt = inc16(k->mon_cnt);
		} else {
			k->mon_cnt = 0U;
		}
		if (k->mon_cnt >= FQ_MON_N) {
			k->mon_fail = true;
		}
	}
	/* FQ-46: sign/status matrix */
	if (k->mon_fail) {
		k->ssm = FQ_SSM_FW;
	} else if (k->res.status == FQ_ST_INVALID) {
		k->ssm = FQ_SSM_NCD;
	} else {
		k->ssm = FQ_SSM_NO;
	}
	low_fuel(k, f->low_wet[t]);
}

static void output(fq_ctx_t *x)
{
	uint32_t st = 0U;
	uint32_t t;
	static const uint32_t lbl[FQ_NT] = {FQ_LBL_LEFT, FQ_LBL_RIGHT};
	static const uint32_t low[FQ_NT] = {FQ_ST_LOW_L, FQ_ST_LOW_R};
	static const uint32_t dis[FQ_NT] = {FQ_ST_DIS_L, FQ_ST_DIS_R};
	static const uint32_t deg[FQ_NT] = {FQ_ST_DEG_L, FQ_ST_DEG_R};
	static const uint32_t fail[FQ_NT] = {FQ_ST_FAIL_L, FQ_ST_FAIL_R};

	for (t = 0U; t < FQ_NT; t++) {
		const fq_tank_t *k = &x->t[t];

		x->words[t] = fq_a429_bnr(lbl[t], k->m_filt, FQ_A429_RANGE_KG, k->ssm);
		if (k->low_warn) {
			st |= low[t];
		}
		if (k->disagree) {
			st |= dis[t];
		}
		if ((k->res.status == FQ_ST_DEGRADED) || (k->failed != 0U)) {
			st |= deg[t];
		}
		if (k->ssm != FQ_SSM_NO) {
			st |= fail[t];
		}
	}
	if (x->xcomp) {
		st |= FQ_ST_XCOMP;
	}
	if (x->nodata >= FQ_NODATA_N) {
		st |= FQ_ST_NODATA;
	}
	/* FQ-47: the total is normal only if both tanks are; a failure warning wins */
	if ((x->t[0].ssm == FQ_SSM_FW) || (x->t[1].ssm == FQ_SSM_FW)) {
		x->total_ssm = FQ_SSM_FW;
	} else if ((x->t[0].ssm == FQ_SSM_NO) && (x->t[1].ssm == FQ_SSM_NO)) {
		x->total_ssm = FQ_SSM_NO;
	} else {
		x->total_ssm = FQ_SSM_NCD;
	}
	x->total_kg = x->t[0].m_filt + x->t[1].m_filt;
	x->words[2] = fq_a429_bnr(FQ_LBL_TOTAL, x->total_kg, FQ_A429_RANGE_KG, x->total_ssm);
	x->status = st;
	x->words[3] = fq_a429_discrete(FQ_LBL_STATUS, st, FQ_SSM_FW); /* discrete word: SSM 00 = normal */
}

void fq_step(fq_ctx_t *x, const fq_frame_t *f)
{
	float eps[FQ_NT];
	bool eps_ok[FQ_NT];
	uint32_t t;

	x->cycles++;
	x->nodata = 0U;
	select_eps(x, f, eps, eps_ok);
	for (t = 0U; t < FQ_NT; t++) {
		tank_step(x, t, f, eps[t], eps_ok[t]);
	}
	output(x);
}

void fq_no_data(fq_ctx_t *x)
{
	x->cycles++;
	x->nodata = inc16(x->nodata);
	if (x->nodata >= FQ_NODATA_N) {
		/* FQ-48: no acquisition data for 0.5 s: no computed data (a failure warning stays) */
		for (uint32_t t = 0U; t < FQ_NT; t++) {
			if (x->t[t].ssm != FQ_SSM_FW) {
				x->t[t].ssm = FQ_SSM_NCD;
			}
		}
	}
	output(x);
}
