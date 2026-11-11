/*
 * ARINC 429 words (FQ-60..FQ-62). Bit numbering of ARINC 429 Part 1, word bit 1
 * = LSB here: bits 1-8 label (sent MSB first, so stored bit-reversed), 9-10 SDI
 * (0), 11-28 BNR data (MSB bit 28), 29 sign, 30-31 SSM, 32 odd parity.
 * SPDX-License-Identifier: MIT
 */
#include "fq/fq.h"

#define DATA_MAX 0x3FFFFU   /* 18 data bits */
#define TWO18 262144.0f      /* 2^18 */
#define DATA_MAX_F 262143.0f

static uint32_t reverse8(uint32_t v)
{
	uint32_t r = 0U;
	uint32_t i;

	for (i = 0U; i < 8U; i++) {
		if ((v & (1U << i)) != 0U) {
			r |= 1U << (7U - i);
		}
	}
	return r;
}

static uint32_t with_parity(uint32_t w)
{
	uint32_t ones = 0U;
	uint32_t i;

	for (i = 0U; i < 31U; i++) {
		ones += (w >> i) & 1U;
	}
	return ((ones & 1U) == 0U) ? (w | 0x80000000U) : w;
}

uint32_t fq_a429_parity_ok(uint32_t word)
{
	uint32_t ones = 0U;
	uint32_t i;

	for (i = 0U; i < 32U; i++) {
		ones += (word >> i) & 1U;
	}
	return ones & 1U;
}

uint32_t fq_a429_bnr(uint32_t label, float value, float range, uint32_t ssm)
{
	/* LSB = range / 2^DATA_BITS; a negative value is two's complement with the sign bit */
	const float lsb = range / TWO18;
	float q = value / lsb;
	uint32_t data;
	uint32_t sign = 0U;

	if (q < 0.0f) {
		sign = 1U;
		q = q + TWO18;
		if (q < 0.0f) {
			q = 0.0f;
		}
	}
	/* also catches a tiny negative value, which would otherwise round into the sign bit */
	if (q > DATA_MAX_F) {
		q = DATA_MAX_F;
	}
	data = (uint32_t)(q + 0.5f);
	return with_parity(reverse8(label & 0xFFU) | (data << 10U) | (sign << 28U) | ((ssm & 3U) << 29U));
}

uint32_t fq_a429_discrete(uint32_t label, uint32_t bits, uint32_t ssm)
{
	return with_parity(reverse8(label & 0xFFU) | ((bits & DATA_MAX) << 10U) | ((ssm & 3U) << 29U));
}

float fq_a429_bnr_value(uint32_t word, float range)
{
	const float lsb = range / TWO18;
	const uint32_t data = (word >> 10U) & DATA_MAX;
	float v = (float)data * lsb;

	if (((word >> 28U) & 1U) != 0U) {
		v -= range;
	}
	return v;
}
