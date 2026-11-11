/*
 * ARINC 429 word tests (FQ-60..FQ-62).
 * SPDX-License-Identifier: MIT
 */
#include "harness.h"

static unsigned rev8(unsigned v)
{
	unsigned r = 0;
	for (int i = 0; i < 8; i++)
		if (v & (1u << i))
			r |= 1u << (7 - i);
	return r;
}

static void test_layout(void)
{
	/* label 247 octal = 0xA7 = 1010 0111: bit 1 carries the label MSB */
	uint32_t w = fq_a429_bnr(FQ_LBL_TOTAL, 0.0f, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_EQ(w & 0xFFu, rev8(0247u));
	CHECK_EQ((w >> 8) & 3u, 0u);           /* SDI */
	CHECK_EQ((w >> 10) & 0x3FFFFu, 0u);    /* data */
	CHECK_EQ((w >> 28) & 1u, 0u);          /* sign */
	CHECK_EQ((w >> 29) & 3u, FQ_SSM_NO);   /* SSM */
	CHECK_EQ(fq_a429_parity_ok(w), 1u);    /* odd parity */
	/* parity bit set or clear as needed */
	uint32_t a = fq_a429_bnr(0001u, 0.0f, 1.0f, FQ_SSM_FW); /* one 1 in the label: parity 0 */
	uint32_t b = fq_a429_bnr(0003u, 0.0f, 1.0f, FQ_SSM_FW); /* two 1s: parity 1 */
	CHECK_EQ(a >> 31, 0u);
	CHECK_EQ(b >> 31, 1u);
	CHECK_EQ(fq_a429_parity_ok(a ^ 0x400u), 0u); /* a single bit error is seen */
}

static void test_bnr(void)
{
	const float lsb = FQ_A429_RANGE_KG / 262144.0f;
	const float vals[] = {0.0f, 1.0f, 123.456f, 744.9f, 1488.0f, 4095.0f};
	for (unsigned i = 0; i < sizeof(vals) / sizeof(vals[0]); i++) {
		uint32_t w = fq_a429_bnr(FQ_LBL_LEFT, vals[i], FQ_A429_RANGE_KG, FQ_SSM_NO);
		CHECK_NEAR(fq_a429_bnr_value(w, FQ_A429_RANGE_KG), vals[i], 0.51 * lsb);
		CHECK_EQ(fq_a429_parity_ok(w), 1u);
	}
	/* negative values: two's complement with the sign bit */
	uint32_t w = fq_a429_bnr(FQ_LBL_LEFT, -10.0f, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_EQ((w >> 28) & 1u, 1u);
	CHECK_NEAR(fq_a429_bnr_value(w, FQ_A429_RANGE_KG), -10.0, 0.51 * lsb);
	/* clamps */
	w = fq_a429_bnr(FQ_LBL_LEFT, 99999.0f, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_EQ((w >> 10) & 0x3FFFFu, 0x3FFFFu);
	w = fq_a429_bnr(FQ_LBL_LEFT, -99999.0f, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_EQ((w >> 10) & 0x3FFFFu, 0u);
	CHECK_EQ((w >> 28) & 1u, 1u);
	/* a tiny negative value must not round into the sign bit */
	w = fq_a429_bnr(FQ_LBL_LEFT, -0.001f, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_NEAR(fq_a429_bnr_value(w, FQ_A429_RANGE_KG), -0.001, lsb);
	/* just below full scale rounds up past the data field: clamped */
	w = fq_a429_bnr(FQ_LBL_LEFT, FQ_A429_RANGE_KG - 0.4f * lsb, FQ_A429_RANGE_KG, FQ_SSM_NO);
	CHECK_EQ((w >> 10) & 0x3FFFFu, 0x3FFFFu);
}

static void test_discrete(void)
{
	uint32_t w = fq_a429_discrete(FQ_LBL_STATUS, FQ_ST_LOW_R | FQ_ST_XCOMP, 0u);
	CHECK_EQ(w & 0xFFu, rev8(0270u));
	CHECK_EQ((w >> 10) & 0x3FFFFu, FQ_ST_LOW_R | FQ_ST_XCOMP);
	CHECK_EQ(fq_a429_parity_ok(w), 1u);
}

void test_a429(void)
{
	test_layout();
	test_bnr();
	test_discrete();
}
