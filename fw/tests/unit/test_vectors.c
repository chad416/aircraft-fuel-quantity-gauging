/*
 * Back-to-back test (FQ-10..FQ-30): the C core against the reference model
 * (model/fqsim/gauge.py) on 160 generated cases - healthy, in-range bias, open,
 * water, no specific force, latched failure, no compensator, densitometer.
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"
#include "vectors.h"

void test_vectors(void)
{
	int mism = 0;

	for (int n = 0; n < N_VEC; n++) {
		const vec_t *v = &vec[n];
		fq_in_t in;
		fq_res_t r;
		float mu = 0.0f;

		memset(&in, 0, sizeof(in));
		in.caps = v->caps;
		in.eps = v->eps;
		in.eps_ok = v->eps_ok != 0;
		in.sf.fx = v->sf[0];
		in.sf.fy = v->sf[1];
		in.sf.fz = v->sf[2];
		in.sf.valid = v->sf_valid != 0;
		in.rho_valid = v->rho_valid != 0;
		in.rho_meas = v->rho;
		in.failed = (uint8_t)v->failed;
		in.hold_valid = v->hold_valid != 0;
		in.hold_sx = v->hold[0];
		in.hold_sy = v->hold[1];
		fq_solve(right(), &in, &r);
		int bad = 0;
		bad |= r.status != v->status;
		if (v->status != FQ_ST_INVALID) {
			bad |= r.excluded != v->excluded;
			bad |= r.n_live != v->n_live;
			bad |= (int)r.fallback != v->fallback;
			bad |= fabs(r.z_ref - v->z_ref) > 2e-4;
			bad |= fabs(r.sx - v->sx) > 2e-4;
			bad |= fabs(r.sy - v->sy) > 2e-4;
			bad |= fabs(r.volume - v->volume) > 1e-4; /* 0.01 % of full scale */
			bad |= fabs(r.mass - v->mass) > 0.1;
		}
		bool ok = fq_monitor(right(), v->caps, v->eps, &in.sf, in.failed, &mu);
		bad |= (int)ok != v->mon_ok;
		if (ok && v->mon_ok)
			bad |= fabs(mu - v->mon_usable) > 1e-4;
		if (bad) {
			mism++;
			printf("vector %d: status %d/%d excl %d/%d live %d/%d fb %d/%d z %g/%g m %g/%g mon %d/%d\n", n,
			       r.status, v->status, r.excluded, v->excluded, r.n_live, v->n_live, r.fallback, v->fallback,
			       (double)r.z_ref, (double)v->z_ref, (double)r.mass, (double)v->mass, ok, v->mon_ok);
		}
		CHECK(!bad);
	}
	printf("back-to-back: %d vectors, %d mismatches\n", N_VEC, mism);
}
