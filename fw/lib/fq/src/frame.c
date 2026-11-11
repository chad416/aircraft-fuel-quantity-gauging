/*
 * Acquisition and output frames (FQ-70..FQ-73): CRC-16/CCITT-FALSE, the
 * acquisition-frame encoder (used by the tests and the rig) and byte-wise
 * parser, and the output frame for the maintenance / test port.
 *
 * Frame: 0xA5 0x5A len type payload[len] crc_hi crc_lo; the CRC covers len,
 * type and payload. Bad CRC, wrong type or wrong length: dropped and counted;
 * the parser then searches for the next sync pair.
 * SPDX-License-Identifier: MIT
 */
#include "fq/fq.h"

uint16_t fq_crc16(const uint8_t *p, uint32_t n)
{
	uint16_t crc = 0xFFFFU;
	uint32_t i;
	uint32_t b;

	for (i = 0U; i < n; i++) {
		crc = (uint16_t)(crc ^ (uint16_t)((uint16_t)p[i] << 8U));
		for (b = 0U; b < 8U; b++) {
			if ((crc & 0x8000U) != 0U) {
				crc = (uint16_t)((uint16_t)(crc << 1U) ^ 0x1021U);
			} else {
				crc = (uint16_t)(crc << 1U);
			}
		}
	}
	return crc;
}

static void put16(uint8_t *p, uint16_t v)
{
	p[0] = (uint8_t)(v >> 8U);
	p[1] = (uint8_t)(v & 0xFFU);
}

static uint16_t get16(const uint8_t *p)
{
	return (uint16_t)((uint16_t)((uint16_t)p[0] << 8U) | (uint16_t)p[1]);
}

static uint16_t to_u16(float v, float scale)
{
	float q = (v * scale) + 0.5f;

	if (q < 0.0f) {
		q = 0.0f;
	} else if (q > 65535.0f) {
		q = 65535.0f;
	} else {
		/* in range */
	}
	return (uint16_t)q;
}

static int16_t to_s16(float v, float scale)
{
	float q = v * scale;

	if (q < -32768.0f) {
		q = -32768.0f;
	} else if (q > 32767.0f) {
		q = 32767.0f;
	} else {
		/* in range */
	}
	return (int16_t)q;
}

static uint32_t finish(uint8_t *buf, uint32_t plen, uint8_t type)
{
	uint16_t crc;

	buf[0] = FQ_SYNC0;
	buf[1] = FQ_SYNC1;
	buf[2] = (uint8_t)plen;
	buf[3] = type;
	crc = fq_crc16(&buf[2], plen + 2U);
	put16(&buf[FQ_HDR_LEN + plen], crc);
	return FQ_HDR_LEN + plen + FQ_CRC_LEN;
}

uint32_t fq_acq_encode(uint8_t seq, const fq_frame_t *f, uint8_t *buf, uint32_t cap)
{
	uint32_t len = 0U;
	uint8_t *p = &buf[FQ_HDR_LEN];

	if (cap >= FQ_MAX_FRAME) {
		uint8_t flags = f->sf.valid ? (uint8_t)FQ_ACQ_SF : 0U;

		flags = f->rho_valid[0] ? (uint8_t)(flags | FQ_ACQ_RHO_L) : flags;
		flags = f->rho_valid[1] ? (uint8_t)(flags | FQ_ACQ_RHO_R) : flags;
		flags = f->low_wet[0] ? (uint8_t)(flags | FQ_ACQ_WET_L) : flags;
		flags = f->low_wet[1] ? (uint8_t)(flags | FQ_ACQ_WET_R) : flags;
		p[0] = seq;
		p[1] = flags;
		for (uint32_t t = 0U; t < FQ_NT; t++) {
			for (uint32_t i = 0U; i < FQ_NP; i++) {
				put16(&p[2U + (2U * ((t * FQ_NP) + i))], to_u16(f->caps[t][i], 100.0f));
			}
			put16(&p[34U + (2U * t)], to_u16(f->comp[t], 100.0f));
			put16(&p[44U + (2U * t)], to_u16(f->rho[t], 10.0f));
		}
		put16(&p[38], (uint16_t)to_s16(f->sf.fx, 1000.0f));
		put16(&p[40], (uint16_t)to_s16(f->sf.fy, 1000.0f));
		put16(&p[42], (uint16_t)to_s16(f->sf.fz, 1000.0f));
		len = finish(buf, FQ_ACQ_LEN, FQ_T_ACQ);
	}
	return len;
}

void fq_parser_init(fq_parser_t *p)
{
	p->pos = 0U;
	p->need = 0U;
	p->crc_errors = 0U;
	p->format_errors = 0U;
	p->frames = 0U;
	p->seq = 0U;
}

static bool decode(fq_parser_t *p, fq_frame_t *f)
{
	const uint32_t plen = (uint32_t)p->buf[2];
	const uint8_t *q = &p->buf[FQ_HDR_LEN];
	bool got = false;
	uint32_t t;
	uint32_t i;

	if (get16(&q[plen]) != fq_crc16(&p->buf[2], plen + 2U)) {
		p->crc_errors++;
	} else if ((p->buf[3] == FQ_T_ACQ) && (plen == FQ_ACQ_LEN)) {
		const uint8_t fl = q[1];

		p->seq = q[0];
		for (t = 0U; t < FQ_NT; t++) {
			for (i = 0U; i < FQ_NP; i++) {
				f->caps[t][i] = (float)get16(&q[2U + (2U * ((t * FQ_NP) + i))]) * 0.01f;
			}
			f->comp[t] = (float)get16(&q[34U + (2U * t)]) * 0.01f;
			f->rho[t] = (float)get16(&q[44U + (2U * t)]) * 0.1f;
		}
		f->sf.fx = (float)(int16_t)get16(&q[38]) * 0.001f;
		f->sf.fy = (float)(int16_t)get16(&q[40]) * 0.001f;
		f->sf.fz = (float)(int16_t)get16(&q[42]) * 0.001f;
		f->sf.valid = ((fl & FQ_ACQ_SF) != 0U) && (f->sf.fz > 0.1f);
		f->rho_valid[0] = (fl & FQ_ACQ_RHO_L) != 0U;
		f->rho_valid[1] = (fl & FQ_ACQ_RHO_R) != 0U;
		f->low_wet[0] = (fl & FQ_ACQ_WET_L) != 0U;
		f->low_wet[1] = (fl & FQ_ACQ_WET_R) != 0U;
		p->frames++;
		got = true;
	} else {
		p->format_errors++;
	}
	return got;
}

bool fq_parser_feed(fq_parser_t *p, uint8_t byte, fq_frame_t *f)
{
	bool got = false;

	if (p->pos == 0U) {
		if (byte == FQ_SYNC0) {
			p->buf[0] = byte;
			p->pos = 1U;
		}
	} else if (p->pos == 1U) {
		if (byte == FQ_SYNC1) {
			p->buf[1] = byte;
			p->pos = 2U;
		} else if (byte != FQ_SYNC0) {
			p->pos = 0U;
		} else {
			/* A5 A5 5A: the second A5 may start the frame */
		}
	} else if (p->pos == 2U) {
		if ((uint32_t)byte > FQ_ACQ_LEN) {
			p->format_errors++;
			p->pos = 0U;
		} else {
			p->buf[2] = byte;
			p->need = FQ_HDR_LEN + (uint32_t)byte + FQ_CRC_LEN;
			p->pos = 3U;
		}
	} else {
		p->buf[p->pos] = byte;
		p->pos++;
		if (p->pos == p->need) {
			got = decode(p, f);
			p->pos = 0U;
		}
	}
	return got;
}

uint32_t fq_out_encode(const fq_ctx_t *x, uint8_t seq, uint8_t *buf, uint32_t cap)
{
	uint32_t len = 0U;
	uint8_t *p = &buf[FQ_HDR_LEN];

	if (cap >= (FQ_HDR_LEN + FQ_OUT_LEN + FQ_CRC_LEN)) {
		p[0] = seq;
		p[1] = (uint8_t)(x->status & 0xFFU);
		p[2] = (uint8_t)((x->status >> 8U) & 0xFFU);
		for (uint32_t t = 0U; t < FQ_NT; t++) {
			const fq_tank_t *k = &x->t[t];
			uint8_t *q = &p[3U + (9U * t)];
			const uint8_t ex = (k->res.excluded < 0) ? 0U : (uint8_t)((uint8_t)k->res.excluded + 1U);

			q[0] = k->res.status;
			q[1] = k->failed;
			put16(&q[2], to_u16(k->m_filt, 10.0f));
			put16(&q[4], to_u16(k->mon_kg, 10.0f));
			put16(&q[6], to_u16(k->res.rho, 10.0f));
			q[8] = (uint8_t)(ex | (uint8_t)(k->ssm << 4U));
		}
		put16(&p[21], to_u16(x->total_kg, 10.0f));
		p[23] = (uint8_t)x->total_ssm;
		for (uint32_t i = 0U; i < 4U; i++) {
			p[24U + (4U * i)] = (uint8_t)(x->words[i] >> 24U);
			p[25U + (4U * i)] = (uint8_t)((x->words[i] >> 16U) & 0xFFU);
			p[26U + (4U * i)] = (uint8_t)((x->words[i] >> 8U) & 0xFFU);
			p[27U + (4U * i)] = (uint8_t)(x->words[i] & 0xFFU);
		}
		len = finish(buf, FQ_OUT_LEN, FQ_T_OUT);
	}
	return len;
}
