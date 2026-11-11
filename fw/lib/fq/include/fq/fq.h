/*
 * Fuel quantity gauge core library: probe classification, fuel-plane fit with
 * residual-based fault detection and exclusion, attitude-table volume, density
 * from the measured permittivity, a diverse monitor lane, fault persistence,
 * low-fuel logic and ARINC 429 output words.
 *
 * Pure C99, no heap, no OS calls; all state lives in caller-owned structs.
 * Requirement IDs (FQ-xx) refer to fw/SRS.md. The algorithm is specified by
 * model/fqsim/gauge.py; constants marked [model] must equal the values there
 * (model/tests/test_fw_consistency.py checks them).
 * SPDX-License-Identifier: MIT
 */
#ifndef FQ_FQ_H
#define FQ_FQ_H

#include <stdbool.h>
#include <stdint.h>

/* ---- Configuration ------------------------------------------------------- */

#define FQ_NT 2U /* tanks: 0 = left (mirrored frame), 1 = right */
#define FQ_NP 8U /* probes per tank */

/* attitude table (generated data in fq_data.c) [model] */
#define FQ_NSX 25U
#define FQ_NSY 17U
#define FQ_NU 65U
#define FQ_SX_MIN (-0.18f)
#define FQ_SX_MAX 0.36f
#define FQ_SY_MIN (-0.14f)
#define FQ_SY_MAX 0.14f

/* classification and residual test [model] */
#define FQ_EPS_MIN 1.85f
#define FQ_EPS_MAX 2.45f
#define FQ_EPS_DEFAULT 2.13f
#define FQ_C_OPEN_PF 2.0f
#define FQ_C_SHORT_PF 2.0f
#define FQ_H_SAT 0.002f
#define FQ_SAT_REL 0.025f
#define FQ_SIGMA_Z 0.0012f
#define FQ_KAPPA 0.012f
#define FQ_DET_MIN 3.0e-3f
#define FQ_SAT_TOL 0.015f

/* computer level (DOSSIER §6.4) */
#define FQ_N_LATCH 3U          /* cycles a probe fault must persist before it is latched */
#define FQ_FILT_ALPHA 0.0125f  /* indicated-mass filter: tau 8 s at 10 Hz */
#define FQ_MON_N 30U           /* cycles of COM/MON disagreement before FQ FAIL (3 s) */
#define FQ_INVALID_N 30U       /* invalid cycles before the filtered value is dropped */
#define FQ_LOW_KG 60.0f        /* low-fuel threshold per tank (usable) */
#define FQ_LOW_N 200U          /* low-fuel persistence: 20 s (slosh) */
#define FQ_DIS_KG 40.0f        /* FQ DISAGREE margin above FQ_LOW_KG */
#define FQ_DIS_N 600U          /* sensor dry 60 s while the gauge reads high */
#define FQ_EPS_XTOL 0.03f      /* left/right compensator cross-check */
#define FQ_NODATA_N 5U         /* cycles without acquisition data before NCD */

/* probe classes */
#define FQ_CL_DRY 0U
#define FQ_CL_LIVE 1U
#define FQ_CL_FULL 2U
#define FQ_CL_OPEN 3U
#define FQ_CL_SHORT 4U
#define FQ_CL_EXCL 5U

/* computation status */
#define FQ_ST_OK 0U
#define FQ_ST_DEGRADED 1U
#define FQ_ST_INVALID 2U

typedef struct {
	float x;    /* m, tank frame */
	float y;
	float zbot; /* bottom of the active length */
	float len;  /* active length */
	float cdry; /* pF */
	float k;    /* pF per metre per unit (eps - 1) */
} fq_probe_cfg_t;

typedef struct {
	fq_probe_cfg_t p[FQ_NP];
	float comp_cdry; /* pF */
	float comp_kl;   /* pF per unit (eps - 1) */
	float xr;        /* table reference point */
	float yr;
	float v_unusable; /* m^3 */
	float fs_kg;      /* full-scale usable mass (design density) */
	float mon_tol_kg; /* COM/MON alarm limit */
	bool mirror;      /* left tank: lateral specific force changes sign */
} fq_tank_cfg_t;

/* generated data (fq_data.c) */
extern const fq_tank_cfg_t fq_tank_cfg[FQ_NT];
extern const float fq_vol[FQ_NSX][FQ_NSY][FQ_NU]; /* m^3 */
extern const float fq_zempty[FQ_NSX][FQ_NSY];
extern const float fq_zfull[FQ_NSX][FQ_NSY];
extern const float fq_chi2[FQ_NP];  /* threshold for 1..8 degrees of freedom */
extern const float fq_r_nom;        /* specific polarisation, m^3/kg */

/* ---- Single-cycle core (solve.c) ------------------------------------------ */

typedef struct {
	float fx; /* body specific force, any unit; x aft, y right, z up */
	float fy;
	float fz;
	bool valid;
} fq_sf_t;

typedef struct {
	float z_ref;
	float sx;
	float sy;
	float chi2; /* weighted residual sum */
} fq_plane_t;

typedef struct {
	const float *caps; /* FQ_NP capacitances, pF */
	float eps;         /* permittivity to use */
	bool eps_ok;       /* false: eps is a substitute (status at best DEGRADED) */
	fq_sf_t sf;
	bool rho_valid; /* densitometer */
	float rho_meas;
	uint8_t failed; /* latched failed probes (bit i) */
	bool hold_valid; /* slopes of the last verified plane */
	float hold_sx;
	float hold_sy;
} fq_in_t;

typedef struct {
	uint8_t status;
	float z_ref;
	float sx;
	float sy;
	float volume; /* m^3 */
	float usable; /* m^3 */
	float rho;    /* kg/m^3 */
	float mass;   /* kg usable */
	int8_t excluded;
	bool detected;
	bool verified;
	bool fallback;
	uint8_t n_live;
	uint8_t sat_bad; /* DRY/FULL probes inconsistent with the plane (bit i) */
	uint8_t cl[FQ_NP];
	float h[FQ_NP];
} fq_res_t;

float fq_rho_from_eps(float eps);
bool fq_comp_eps(const fq_tank_cfg_t *c, float c_comp, float *eps);
void fq_classify(const fq_tank_cfg_t *c, const float *caps, float eps, float *h, uint8_t *cl);
float fq_weight(float h);
bool fq_fit_plane(const fq_tank_cfg_t *c, uint8_t mask, const float *zs, const float *w, fq_plane_t *pl);
bool fq_in_table(float sx, float sy);
float fq_table_volume(float z_ref, float sx, float sy);
void fq_sf_slopes(const fq_tank_cfg_t *c, const fq_sf_t *sf, float *sx, float *sy);
void fq_solve(const fq_tank_cfg_t *c, const fq_in_t *in, fq_res_t *r);
bool fq_monitor(const fq_tank_cfg_t *c, const float *caps, float eps, const fq_sf_t *sf, uint8_t failed,
		float *v_usable);

/* ---- ARINC 429 words (a429.c) ---------------------------------------------- */

#define FQ_SSM_FW 0U  /* failure warning */
#define FQ_SSM_NCD 1U /* no computed data */
#define FQ_SSM_FT 2U  /* functional test */
#define FQ_SSM_NO 3U  /* normal operation */

#define FQ_LBL_LEFT 0256U  /* octal labels (A: assigned in the interface control document) */
#define FQ_LBL_RIGHT 0257U
#define FQ_LBL_TOTAL 0247U
#define FQ_LBL_STATUS 0270U
#define FQ_A429_RANGE_KG 4096.0f /* BNR full scale; 18 data bits: LSB 1/64 kg */

uint32_t fq_a429_bnr(uint32_t label, float value, float range, uint32_t ssm);
uint32_t fq_a429_discrete(uint32_t label, uint32_t bits, uint32_t ssm);
uint32_t fq_a429_parity_ok(uint32_t word);
float fq_a429_bnr_value(uint32_t word, float range);

/* ---- Gauge computer (fqc.c) ------------------------------------------------- */

/* status-word bits (label 270) */
#define FQ_ST_LOW_L 0x001U
#define FQ_ST_LOW_R 0x002U
#define FQ_ST_DIS_L 0x004U
#define FQ_ST_DIS_R 0x008U
#define FQ_ST_DEG_L 0x010U
#define FQ_ST_DEG_R 0x020U
#define FQ_ST_FAIL_L 0x040U
#define FQ_ST_FAIL_R 0x080U
#define FQ_ST_XCOMP 0x100U
#define FQ_ST_NODATA 0x200U

typedef struct {
	float caps[FQ_NT][FQ_NP];
	float comp[FQ_NT];
	fq_sf_t sf;
	bool rho_valid[FQ_NT];
	float rho[FQ_NT];
	bool low_wet[FQ_NT]; /* independent low-level sensor: true = wet */
} fq_frame_t;

typedef struct {
	uint8_t failed;
	uint8_t cnt[FQ_NP];
	bool hold_valid;
	float hold_sx;
	float hold_sy;
	bool eps_valid;
	float eps_last;
	bool m_valid;
	float m_filt;
	uint16_t inv_cnt;
	uint16_t mon_cnt;
	bool mon_fail;
	float mon_kg;
	bool mon_ok;
	uint16_t low_cnt;  /* sensor dry */
	uint16_t lowc_cnt; /* computed below the threshold */
	bool low_warn;
	bool disagree;
	uint32_t ssm;
	fq_res_t res;
} fq_tank_t;

typedef struct {
	fq_tank_t t[FQ_NT];
	uint32_t cycles;
	uint16_t nodata;
	bool xcomp;
	uint32_t status;
	uint32_t total_ssm;
	float total_kg;
	uint32_t words[4]; /* left, right, total, status */
} fq_ctx_t;

void fq_init(fq_ctx_t *x);
void fq_step(fq_ctx_t *x, const fq_frame_t *f);
void fq_no_data(fq_ctx_t *x);

/* ---- Acquisition and output frames (frame.c) -------------------------------- */

#define FQ_SYNC0 0xA5U
#define FQ_SYNC1 0x5AU
#define FQ_T_ACQ 0x10U /* transmitter concentrator -> gauge computer, every 100 ms */
#define FQ_T_OUT 0x90U /* gauge computer -> maintenance / test port */
#define FQ_HDR_LEN 4U
#define FQ_CRC_LEN 2U
#define FQ_ACQ_LEN 48U /* seq flags caps[16](2) comp[2](2) sf[3](2) rho[2](2) */
#define FQ_OUT_LEN 40U
#define FQ_MAX_FRAME (FQ_HDR_LEN + FQ_ACQ_LEN + FQ_CRC_LEN)
#define FQ_ACQ_SF 0x01U
#define FQ_ACQ_RHO_L 0x02U
#define FQ_ACQ_RHO_R 0x04U
#define FQ_ACQ_WET_L 0x08U
#define FQ_ACQ_WET_R 0x10U

typedef struct {
	uint32_t pos;
	uint32_t need;
	uint32_t crc_errors;
	uint32_t format_errors;
	uint32_t frames;
	uint8_t seq;
	uint8_t buf[FQ_MAX_FRAME];
} fq_parser_t;

uint16_t fq_crc16(const uint8_t *p, uint32_t n);
uint32_t fq_acq_encode(uint8_t seq, const fq_frame_t *f, uint8_t *buf, uint32_t cap);
void fq_parser_init(fq_parser_t *p);
bool fq_parser_feed(fq_parser_t *p, uint8_t byte, fq_frame_t *f);
uint32_t fq_out_encode(const fq_ctx_t *x, uint8_t seq, uint8_t *buf, uint32_t cap);

#endif
