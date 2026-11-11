/*
 * Test runner and synthetic tank readings.
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"

int g_checks;
int g_failures;

const fq_tank_cfg_t *right(void)
{
	return &fq_tank_cfg[1];
}

const fq_tank_cfg_t *left(void)
{
	return &fq_tank_cfg[0];
}

void plane_caps(const fq_tank_cfg_t *c, float z_ref, float sx, float sy, float eps, float *caps)
{
	for (unsigned i = 0; i < FQ_NP; i++) {
		const fq_probe_cfg_t *p = &c->p[i];
		float zs = z_ref + sx * (p->x - c->xr) + sy * (p->y - c->yr);
		float h = zs - p->zbot;
		if (h < 0.0f)
			h = 0.0f;
		if (h > p->len)
			h = p->len;
		caps[i] = p->cdry + p->k * (eps - 1.0f) * h;
	}
}

float comp_caps(const fq_tank_cfg_t *c, float eps)
{
	return c->comp_cdry + c->comp_kl * (eps - 1.0f);
}

float z_for_probe(const fq_tank_cfg_t *c, unsigned i, float f, float sx, float sy)
{
	const fq_probe_cfg_t *p = &c->p[i];
	return p->zbot + f * p->len - sx * (p->x - c->xr) - sy * (p->y - c->yr);
}

void frame_for(fq_frame_t *f, float zL, float zR, float sx, float sy, float eps)
{
	memset(f, 0, sizeof(*f));
	/* left tank: mirrored frame, the lateral slope changes sign */
	plane_caps(left(), zL, sx, -sy, eps, f->caps[0]);
	plane_caps(right(), zR, sx, sy, eps, f->caps[1]);
	f->comp[0] = comp_caps(left(), eps);
	f->comp[1] = comp_caps(right(), eps);
	f->sf.fx = -sx;
	f->sf.fy = -sy;
	f->sf.fz = 1.0f;
	f->sf.valid = true;
	f->low_wet[0] = true;
	f->low_wet[1] = true;
}

int main(void)
{
	test_frame();
	test_a429();
	test_solve();
	test_vectors();
	test_fqc();
	printf("%d checks, %d failures\n", g_checks, g_failures);
	return g_failures ? 1 : 0;
}
