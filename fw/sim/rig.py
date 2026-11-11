# Deterministic test rig for the fuel gauge computer (IronPython 2.7, inside the
# Renode monitor). It replaces the rest of the aircraft:
#
#   - probe-transmitter concentrator on LPUART3: one acquisition frame every
#     100 ms of virtual time, replayed from a scenario CSV made by
#     model/studies/s8_export.py (probe and compensator capacitances, specific
#     force, low-level sensors, true masses); rows with send = 0 are a data gap
#   - output decoder: tank masses, sign/status, status word, ARINC 429 words,
#     logged with the true masses of the row that was last sent
#
# Robot keywords drive it with `python "rig...."` monitor commands.

import clr

clr.AddReference("System")
from Antmicro.Renode.Time import TimeInterval  # noqa: E402
from System import Action  # noqa: E402

SYNC0, SYNC1, T_ACQ, T_OUT = 0xA5, 0x5A, 0x10, 0x90
OUT_LEN = 40


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def u16(v):
    v = int(round(v))
    v = max(0, min(65535, v))
    return [(v >> 8) & 0xFF, v & 0xFF]


def s16(v):
    v = int(v)
    v = max(-32768, min(32767, v))
    v &= 0xFFFF
    return [(v >> 8) & 0xFF, v & 0xFF]


def parity_ok(w):
    n = 0
    for i in range(32):
        n += (w >> i) & 1
    return n % 2 == 1


class Rig(object):
    def __init__(self, machine, csv):
        self.m = machine
        self.uart = machine["sysbus.lpuart3"]
        self.uart.CharReceived += self._on_char
        self.rows = []
        f = open(csv)
        head = f.readline().strip().split(",")
        for line in f:
            vals = [float(x) for x in line.strip().split(",")]
            self.rows.append(dict(zip(head, vals)))
        f.close()
        self.k = 0
        self.seq = 0
        self.sent = 0
        self.last_row = None
        self.buf = []
        self.need = 0
        self.outs = 0
        self.crc_bad = 0
        self.parity_bad = 0
        # log rows: t_ms, row_t, mL, mR, ssmL, ssmR, total, total_ssm, status, failedL, failedR,
        # truthL, truthR, total word
        self.log = []
        self._schedule()

    def now_ms(self):
        return self.m.ElapsedVirtualTime.TimeElapsed.TotalMilliseconds

    # ---- concentrator ---------------------------------------------------------
    def _schedule(self):
        self.m.ScheduleAction(TimeInterval.FromMilliseconds(100), Action[TimeInterval](self._tick))

    def _tick(self, _i):
        self._schedule()
        if self.k >= len(self.rows):
            return
        r = self.rows[self.k]
        self.k += 1
        if r["send"] < 0.5:
            return
        p = [self.seq & 0xFF, 0]
        fl = 0
        if r["sf"] > 0.5:
            fl |= 0x01
        if r["wetL"] > 0.5:
            fl |= 0x08
        if r["wetR"] > 0.5:
            fl |= 0x10
        p[1] = fl
        for side in ("L", "R"):
            for i in range(1, 9):
                p += u16(r["c%s%d" % (side, i)] * 100.0)
        p += u16(r["compL"] * 100.0) + u16(r["compR"] * 100.0)
        p += s16(r["fx"] * 1000.0) + s16(r["fy"] * 1000.0) + s16(r["fz"] * 1000.0)
        p += u16(r["rhoL"] * 10.0) + u16(r["rhoR"] * 10.0)
        body = [len(p), T_ACQ] + p
        c = crc16(body)
        for b in [SYNC0, SYNC1] + body + [c >> 8, c & 0xFF]:
            self.uart.WriteChar(b)
        self.seq += 1
        self.sent += 1
        self.last_row = r

    # ---- output decoder -----------------------------------------------------------
    def _on_char(self, c):
        b = int(c) & 0xFF
        buf = self.buf
        if len(buf) == 0:
            if b == SYNC0:
                buf.append(b)
            return
        if len(buf) == 1:
            if b == SYNC1:
                buf.append(b)
            elif b != SYNC0:
                del buf[:]
            return
        buf.append(b)
        if len(buf) == 3:
            self.need = 4 + b + 2
        if len(buf) >= 4 and len(buf) == self.need:
            body = buf[2:-2]
            if crc16(body) == ((buf[-2] << 8) | buf[-1]) and buf[3] == T_OUT and buf[2] == OUT_LEN:
                self._decode(buf[4:-2])
            else:
                self.crc_bad += 1
            del buf[:]

    def _decode(self, p):
        status = p[1] | (p[2] << 8)
        tk = []
        for t in range(2):
            q = p[3 + 9 * t : 12 + 9 * t]
            tk.append(
                {
                    "st": q[0],
                    "failed": q[1],
                    "m": ((q[2] << 8) | q[3]) / 10.0,
                    "mon": ((q[4] << 8) | q[5]) / 10.0,
                    "rho": ((q[6] << 8) | q[7]) / 10.0,
                    "excl": (q[8] & 0x0F) - 1,
                    "ssm": q[8] >> 4,
                }
            )
        total = ((p[21] << 8) | p[22]) / 10.0
        words = []
        for i in range(4):
            w = (p[24 + 4 * i] << 24) | (p[25 + 4 * i] << 16) | (p[26 + 4 * i] << 8) | p[27 + 4 * i]
            words.append(w)
            if not parity_ok(w):
                self.parity_bad += 1
        r = self.last_row
        tl = r["mL"] if r else -1.0
        tr = r["mR"] if r else -1.0
        rt = r["t"] if r else -1.0
        self.log.append(
            (
                self.now_ms(),
                rt,
                tk[0]["m"],
                tk[1]["m"],
                tk[0]["ssm"],
                tk[1]["ssm"],
                total,
                p[23],
                status,
                tk[0]["failed"],
                tk[1]["failed"],
                tl,
                tr,
                words[2],
            )
        )
        self.outs += 1

    # ---- queries for the Robot tests --------------------------------------------------
    def last(self, i):
        return self.log[-1][int(i)] if self.log else -1

    def max_err(self, after_s, before_s=1e9):
        """Largest |indicated - true| per tank (kg) over the rows sent in [after, before)."""
        e = 0.0
        for x in self.log:
            if after_s <= x[1] < before_s:
                e = max(e, abs(x[2] - x[11]), abs(x[3] - x[12]))
        return e

    def max_over(self, after_s, before_s=1e9):
        """Largest indicated-minus-true (kg, signed: positive = reads high)."""
        e = -1e9
        for x in self.log:
            if after_s <= x[1] < before_s:
                e = max(e, x[2] - x[11], x[3] - x[12])
        return e

    def all_ssm_normal(self, after_s, before_s=1e9):
        for x in self.log:
            if after_s <= x[1] < before_s and (x[4] != 3 or x[5] != 3 or x[7] != 3):
                return False
        return True

    def abnormal(self, after_s, before_s=1e9, n=6):
        """The first n outputs (row time, ssm L, ssm R, total ssm, status) that are not all normal."""
        out = []
        for x in self.log:
            if after_s <= x[1] < before_s and (x[4] != 3 or x[5] != 3 or x[7] != 3):
                out.append((x[1], x[4], x[5], x[7], x[8]))
                if len(out) >= n:
                    break
        return out

    def first_status_time(self, bit):
        """Virtual time (ms) of the first output with the status bit set, or -1."""
        for x in self.log:
            if x[8] & int(bit):
                return x[0]
        return -1.0

    def first_failed_time(self, side, mask):
        for x in self.log:
            if x[9 + int(side)] & int(mask):
                return x[0]
        return -1.0

    def first_ssm_time(self, side, ssm, after_ms=0.0):
        for x in self.log:
            if x[0] >= float(after_ms) and x[4 + int(side)] == int(ssm):
                return x[0]
        return -1.0

    def first_row_time_below(self, side, kg):
        """Virtual time (ms) when the truth of the sent row first went below kg."""
        for x in self.log:
            if x[11 + int(side)] >= 0 and x[11 + int(side)] < float(kg):
                return x[0]
        return -1.0

    def a429_total(self):
        """Total mass decoded from the last ARINC 429 word (label 247, BNR, 4096 kg range)."""
        if not self.log:
            return -1.0
        w = self.log[-1][13]
        data = (w >> 10) & 0x3FFFF
        v = data * 4096.0 / 262144.0
        if (w >> 28) & 1:
            v -= 4096.0
        return v

    def _sym(self, name):
        return self.m["sysbus"].GetSymbolAddress(name)

    def read_u32(self, name):
        return int(self.m["sysbus"].ReadDoubleWord(self._sym(name)))
