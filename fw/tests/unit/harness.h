/*
 * Minimal test harness and helpers for the gauge library tests.
 * SPDX-License-Identifier: MIT
 */
#ifndef FQ_TEST_HARNESS_H
#define FQ_TEST_HARNESS_H

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "fq/fq.h"

extern int g_checks;
extern int g_failures;

#define CHECK(cond)                                                                    \
	do {                                                                           \
		g_checks++;                                                            \
		if (!(cond)) {                                                         \
			g_failures++;                                                  \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);         \
		}                                                                      \
	} while (0)

#define CHECK_EQ(a, b)                                                                 \
	do {                                                                           \
		long long _a = (long long)(a);                                         \
		long long _b = (long long)(b);                                         \
		g_checks++;                                                            \
		if (_a != _b) {                                                        \
			g_failures++;                                                  \
			printf("FAIL %s:%d: %s == %s (%lld != %lld)\n", __FILE__,      \
			       __LINE__, #a, #b, _a, _b);                              \
		}                                                                      \
	} while (0)

#define CHECK_NEAR(a, b, tol)                                                          \
	do {                                                                           \
		double _a = (double)(a);                                               \
		double _b = (double)(b);                                               \
		g_checks++;                                                            \
		if (fabs(_a - _b) > (double)(tol)) {                                   \
			g_failures++;                                                  \
			printf("FAIL %s:%d: %s ~ %s (%g vs %g, tol %g)\n", __FILE__,    \
			       __LINE__, #a, #b, _a, _b, (double)(tol));               \
		}                                                                      \
	} while (0)

/* right tank configuration and a synthetic reading for a flat plane */
const fq_tank_cfg_t *right(void);
const fq_tank_cfg_t *left(void);
/* capacitances (pF) of every probe of tank c for the plane z = z_ref + sx dx + sy dy */
void plane_caps(const fq_tank_cfg_t *c, float z_ref, float sx, float sy, float eps, float *caps);
float comp_caps(const fq_tank_cfg_t *c, float eps);
/* a plane height that wets probe i to fraction f of its length, slopes given */
float z_for_probe(const fq_tank_cfg_t *c, unsigned i, float f, float sx, float sy);
void frame_for(fq_frame_t *f, float zL, float zR, float sx, float sy, float eps);

void test_frame(void);
void test_a429(void);
void test_solve(void);
void test_vectors(void);
void test_fqc(void);

#endif
