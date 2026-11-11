/*
 * One computation cycle for one tank (FQ-10..FQ-27): permittivity window,
 * probe classification, weighted least-squares fuel plane, residual test with
 * leave-one-out exclusion, DRY/FULL consistency, specific-force fallback,
 * trilinear attitude table, usable volume, density and mass; and the diverse
 * monitor lane (FQ-30). Mirrors model/fqsim/gauge.py.
 * SPDX-License-Identifier: MIT
 */
#include "fq/fq.h"

static float clampf(float v, float lo, float hi)
{
	float r = v;

	if (r < lo) {
		r = lo;
	} else if (r > hi) {
		r = hi;
	} else {
		/* inside */
	}
	return r;
}

float fq_rho_from_eps(float eps)
{
	/* Clausius-Mossotti: (eps - 1) / (eps + 2) = r rho */
	return ((eps - 1.0f) / (eps + 2.0f)) / fq_r_nom;
}

bool fq_comp_eps(const fq_tank_cfg_t *c, float c_comp, float *eps)
{
	const float e = 1.0f + ((c_comp - c->comp_cdry) / c->comp_kl);
	bool ok = false;

	if ((e >= FQ_EPS_MIN) && (e <= FQ_EPS_MAX)) {
		*eps = e;
		ok = true;
	}
	return ok;
}

void fq_classify(const fq_tank_cfg_t *c, const float *caps, float eps, float *h, uint8_t *cl)
{
	uint32_t i;

	for (i = 0U; i < FQ_NP; i++) {
		const fq_probe_cfg_t *p = &c->p[i];
		const float full_max = p->cdry + (p->k * (FQ_EPS_MAX - 1.0f) * p->len) + FQ_C_SHORT_PF;

		h[i] = 0.0f;
		if (caps[i] < (p->cdry - FQ_C_OPEN_PF)) {
			cl[i] = FQ_CL_OPEN;
		} else if (caps[i] > full_max) {
			cl[i] = FQ_CL_SHORT;
		} else {
			h[i] = (caps[i] - p->cdry) / (p->k * (eps - 1.0f));
			if (h[i] <= FQ_H_SAT) {
				cl[i] = FQ_CL_DRY;
			} else if (h[i] >= ((p->len * (1.0f - FQ_SAT_REL)) - FQ_H_SAT)) {
				cl[i] = FQ_CL_FULL;
			} else {
				cl[i] = FQ_CL_LIVE;
			}
		}
	}
}

float fq_weight(float h)
{
	return 1.0f / ((FQ_SIGMA_Z * FQ_SIGMA_Z) + ((FQ_KAPPA * h) * (FQ_KAPPA * h)));
}

bool fq_fit_plane(const fq_tank_cfg_t *c, uint8_t mask, const float *zs, const float *w, fq_plane_t *pl)
{
	float sw = 0.0f;
	float mx = 0.0f;
	float my = 0.0f;
	float mz = 0.0f;
	uint32_t n = 0U;
	bool ok = false;

	for (uint32_t i = 0U; i < FQ_NP; i++) {
		if ((mask & (1U << i)) != 0U) {
			n++;
			sw += w[i];
			mx += w[i] * (c->p[i].x - c->xr);
			my += w[i] * (c->p[i].y - c->yr);
			mz += w[i] * zs[i];
		}
	}
	if (n >= 3U) {
		float sxx = 0.0f;
		float syy = 0.0f;
		float sxy = 0.0f;
		float sxz = 0.0f;
		float syz = 0.0f;
		float det;

		mx /= sw;
		my /= sw;
		mz /= sw;
		for (uint32_t i = 0U; i < FQ_NP; i++) {
			if ((mask & (1U << i)) != 0U) {
				const float dx = (c->p[i].x - c->xr) - mx;
				const float dy = (c->p[i].y - c->yr) - my;
				const float dz = zs[i] - mz;

				sxx += w[i] * dx * dx;
				syy += w[i] * dy * dy;
				sxy += w[i] * dx * dy;
				sxz += w[i] * dx * dz;
				syz += w[i] * dy * dz;
			}
		}
		sxx /= sw;
		syy /= sw;
		sxy /= sw;
		sxz /= sw;
		syz /= sw;
		det = (sxx * syy) - (sxy * sxy);
		if (det >= FQ_DET_MIN) {
			float chi = 0.0f;

			pl->sx = ((sxz * syy) - (syz * sxy)) / det;
			pl->sy = ((syz * sxx) - (sxz * sxy)) / det;
			pl->z_ref = mz - (pl->sx * mx) - (pl->sy * my);
			for (uint32_t i = 0U; i < FQ_NP; i++) {
				if ((mask & (1U << i)) != 0U) {
					const float r = zs[i] - (pl->z_ref + (pl->sx * (c->p[i].x - c->xr)) +
								 (pl->sy * (c->p[i].y - c->yr)));
					chi += w[i] * r * r;
				}
			}
			pl->chi2 = chi;
			ok = true;
		}
	}
	return ok;
}

bool fq_in_table(float sx, float sy)
{
	return (sx >= FQ_SX_MIN) && (sx <= FQ_SX_MAX) && (sy >= FQ_SY_MIN) && (sy <= FQ_SY_MAX);
}

static void locate(float v, float lo, float hi, uint32_t n, uint32_t *i, float *f)
{
	const float t = ((clampf(v, lo, hi) - lo) / (hi - lo)) * ((float)n - 1.0f);
	uint32_t k = (uint32_t)t;

	if (k > (n - 2U)) {
		k = n - 2U;
	}
	*i = k;
	*f = t - (float)k;
}

float fq_table_volume(float z_ref, float sx, float sy)
{
	uint32_t i;
	uint32_t j;
	uint32_t a;
	uint32_t b;
	float fx;
	float fy;
	float v = 0.0f;

	locate(sx, FQ_SX_MIN, FQ_SX_MAX, FQ_NSX, &i, &fx);
	locate(sy, FQ_SY_MIN, FQ_SY_MAX, FQ_NSY, &j, &fy);
	for (a = 0U; a < 2U; a++) {
		for (b = 0U; b < 2U; b++) {
			const float wi = (a == 0U) ? (1.0f - fx) : fx;
			const float wj = (b == 0U) ? (1.0f - fy) : fy;
			const float ze = fq_zempty[i + a][j + b];
			const float zf = fq_zfull[i + a][j + b];
			const float u = clampf((z_ref - ze) / (zf - ze), 0.0f, 1.0f);
			uint32_t k;
			float fu;

			locate(u, 0.0f, 1.0f, FQ_NU, &k, &fu);
			v += wi * wj * ((fq_vol[i + a][j + b][k] * (1.0f - fu)) + (fq_vol[i + a][j + b][k + 1U] * fu));
		}
	}
	return v;
}

void fq_sf_slopes(const fq_tank_cfg_t *c, const fq_sf_t *sf, float *sx, float *sy)
{
	const float y = -sf->fy / sf->fz;

	*sx = -sf->fx / sf->fz;
	*sy = c->mirror ? -y : y;
}

static float plane_at(const fq_tank_cfg_t *c, uint32_t i, float z_ref, float sx, float sy)
{
	return z_ref + (sx * (c->p[i].x - c->xr)) + (sy * (c->p[i].y - c->yr));
}

static uint32_t count_bits(uint8_t m)
{
	uint32_t n = 0U;
	uint32_t i;

	for (i = 0U; i < FQ_NP; i++) {
		if ((m & (1U << i)) != 0U) {
			n++;
		}
	}
	return n;
}

/* Leave-one-out search: the LIVE probe whose removal gives the smallest
 * residual; returns false if no subset fixes a plane. */
static bool best_subset(const fq_tank_cfg_t *c, uint8_t live, const float *zs, const float *w, fq_plane_t *best,
			uint32_t *jbest)
{
	bool found = false;

	for (uint32_t j = 0U; j < FQ_NP; j++) {
		fq_plane_t p;
		const uint8_t sub = (uint8_t)(live & (uint8_t)~(1U << j));

		if ((sub != live) && fq_fit_plane(c, sub, zs, w, &p)) {
			if ((!found) || (p.chi2 < best->chi2)) {
				*best = p;
				*jbest = j;
				found = true;
			}
		}
	}
	return found;
}

/* Residual test and exclusion (FQ-14, FQ-15). Returns false when the tank is invalid. */
static bool residual_test(const fq_tank_cfg_t *c, uint8_t *live, const float *zs, const float *w, fq_plane_t *pl,
			  fq_res_t *r)
{
	const uint32_t n = count_bits(*live);
	bool ok = true;

	if (n >= 4U) {
		if (pl->chi2 > fq_chi2[n - 4U]) {
			fq_plane_t best = {0.0f, 0.0f, 0.0f, 0.0f};
			uint32_t jbest = 0U;
			bool found = false;

			r->detected = true;
			if (n >= 5U) {
				found = best_subset(c, *live, zs, w, &best, &jbest);
			}
			if (found && (best.chi2 <= fq_chi2[n - 5U])) {
				r->excluded = (int8_t)jbest;
				r->cl[jbest] = FQ_CL_EXCL;
				*live = (uint8_t)(*live & (uint8_t)~(1U << jbest));
				*pl = best;
				r->verified = (n - 1U) >= 4U;
			} else {
				ok = false;
			}
		} else {
			r->verified = true;
		}
	}
	return ok;
}

/* DRY/FULL probes against the plane (FQ-16). */
static uint8_t saturated_check(const fq_tank_cfg_t *c, const fq_res_t *r, const fq_plane_t *pl)
{
	uint8_t bad = 0U;
	uint32_t i;

	for (i = 0U; i < FQ_NP; i++) {
		const float zp = plane_at(c, i, pl->z_ref, pl->sx, pl->sy);

		if ((r->cl[i] == FQ_CL_DRY) && (zp > (c->p[i].zbot + FQ_SAT_TOL))) {
			bad = (uint8_t)(bad | (uint8_t)(1U << i));
		}
		if ((r->cl[i] == FQ_CL_FULL) && (zp < ((c->p[i].zbot + c->p[i].len) - FQ_SAT_TOL))) {
			bad = (uint8_t)(bad | (uint8_t)(1U << i));
		}
	}
	return bad;
}

/* Fallback plane from given slopes (FQ-17). Returns false if no probe is usable. */
static bool fallback_plane(const fq_tank_cfg_t *c, const fq_res_t *r, uint8_t live, const float *zs, float sx,
			   float sy, fq_plane_t *pl)
{
	uint32_t i;
	uint32_t n = 0U;
	uint32_t nfull = 0U;
	uint32_t nusable = 0U;
	float sum = 0.0f;
	float zmax = -1000.0f;
	bool ok = true;

	for (i = 0U; i < FQ_NP; i++) {
		if (r->cl[i] <= FQ_CL_FULL) {
			nusable++;
		}
		if ((live & (1U << i)) != 0U) {
			sum += zs[i] - (sx * (c->p[i].x - c->xr)) - (sy * (c->p[i].y - c->yr));
			n++;
		} else if (r->cl[i] == FQ_CL_FULL) {
			const float z = (c->p[i].zbot + c->p[i].len) - (sx * (c->p[i].x - c->xr)) -
					(sy * (c->p[i].y - c->yr));
			if (z > zmax) {
				zmax = z;
			}
			nfull++;
		} else {
			/* DRY, failed or range fault */
		}
	}
	pl->sx = sx;
	pl->sy = sy;
	pl->chi2 = 0.0f;
	if (nusable == 0U) {
		ok = false;
	} else if (n > 0U) {
		pl->z_ref = sum / (float)n;
	} else if (nfull > 0U) {
		pl->z_ref = zmax; /* lowest plane covering every FULL probe: indicated <= true */
	} else {
		pl->z_ref = -1000.0f; /* all DRY: report empty */
	}
	return ok;
}

void fq_solve(const fq_tank_cfg_t *c, const fq_in_t *in, fq_res_t *r)
{
	float zs[FQ_NP];
	float w[FQ_NP];
	uint8_t live = 0U;
	uint32_t i;
	fq_plane_t pl = {0.0f, 0.0f, 0.0f, 0.0f};
	bool have = false;
	bool ok = true;

	r->status = in->eps_ok ? (uint8_t)FQ_ST_OK : (uint8_t)FQ_ST_DEGRADED;
	r->excluded = -1;
	r->detected = false;
	r->verified = false;
	r->fallback = false;
	r->sat_bad = 0U;
	r->z_ref = 0.0f;
	r->sx = 0.0f;
	r->sy = 0.0f;
	r->volume = 0.0f;
	r->usable = 0.0f;
	r->rho = 0.0f;
	r->mass = 0.0f;
	fq_classify(c, in->caps, in->eps, r->h, r->cl);
	for (i = 0U; i < FQ_NP; i++) {
		if ((in->failed & (1U << i)) != 0U) {
			r->cl[i] = FQ_CL_EXCL;
		}
		zs[i] = c->p[i].zbot + r->h[i];
		w[i] = fq_weight(r->h[i]);
		if (r->cl[i] == FQ_CL_LIVE) {
			live = (uint8_t)(live | (uint8_t)(1U << i));
		}
	}
	r->n_live = (uint8_t)count_bits(live);
	if (r->n_live >= 3U) {
		have = fq_fit_plane(c, live, zs, w, &pl);
	}
	if (have) {
		ok = residual_test(c, &live, zs, w, &pl, r);
		r->n_live = (uint8_t)count_bits(live);
		if (ok) {
			r->sat_bad = saturated_check(c, r, &pl);
			if ((r->sat_bad != 0U) && !r->verified) {
				/* an unverified plane that a DRY/FULL probe contradicts: fallback */
				have = false;
				r->sat_bad = 0U;
			}
		}
	}
	if (ok && !have) {
		float sx = 0.0f;
		float sy = 0.0f;

		if (in->sf.valid) {
			fq_sf_slopes(c, &in->sf, &sx, &sy);
		} else if (in->hold_valid) {
			sx = in->hold_sx;
			sy = in->hold_sy;
		} else {
			ok = false;
		}
		if (ok) {
			ok = fallback_plane(c, r, live, zs, sx, sy, &pl);
			r->fallback = true;
			r->status = FQ_ST_DEGRADED;
		}
	}
	if (ok && fq_in_table(pl.sx, pl.sy)) {
		r->z_ref = pl.z_ref;
		r->sx = pl.sx;
		r->sy = pl.sy;
		r->volume = fq_table_volume(pl.z_ref, pl.sx, pl.sy);
		r->usable = (r->volume > c->v_unusable) ? (r->volume - c->v_unusable) : 0.0f;
		r->rho = in->rho_valid ? in->rho_meas : fq_rho_from_eps(in->eps);
		r->mass = r->usable * r->rho;
	} else {
		r->status = FQ_ST_INVALID;
	}
}

bool fq_monitor(const fq_tank_cfg_t *c, const float *caps, float eps, const fq_sf_t *sf, uint8_t failed,
		float *v_usable)
{
	float sx = 0.0f;
	float sy = 0.0f;
	bool ok = false;

	if (sf->valid) {
		fq_sf_slopes(c, sf, &sx, &sy);
		if (fq_in_table(sx, sy)) {
			float h[FQ_NP];
			uint8_t cl[FQ_NP];
			float off[FQ_NP];
			uint32_t n = 0U;

			fq_classify(c, caps, eps, h, cl);
			for (uint32_t i = 0U; i < FQ_NP; i++) {
				if ((cl[i] == FQ_CL_LIVE) && ((failed & (1U << i)) == 0U)) {
					/* insertion into the sorted list */
					const float v = (c->p[i].zbot + h[i]) - (sx * (c->p[i].x - c->xr)) -
							(sy * (c->p[i].y - c->yr));
					uint32_t k = n;

					while ((k > 0U) && (off[k - 1U] > v)) {
						off[k] = off[k - 1U];
						k--;
					}
					off[k] = v;
					n++;
				}
			}
			if (n > 0U) {
				const float z = ((n % 2U) == 1U) ? off[n / 2U]
								 : (0.5f * (off[(n / 2U) - 1U] + off[n / 2U]));
				const float vol = fq_table_volume(z, sx, sy);

				*v_usable = (vol > c->v_unusable) ? (vol - c->v_unusable) : 0.0f;
				ok = true;
			}
		}
	}
	return ok;
}
