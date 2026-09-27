"""HP 12c compatible RPN financial engine.

Stack, storage, and financial behavior follow the HP 12c owner's handbook:
four-level stack, cash-flow sign convention, BEGIN/END payments, odd-period
TVM, amortization rounded to the display, NPV/IRR, actual/actual bonds,
depreciation, calendar, statistics, and 99-step keystroke programming.
"""

from __future__ import annotations

import calendar
import datetime as dt
import math
from decimal import Decimal, ROUND_HALF_UP

MAX_MAG = Decimal("9.999999999e99")
DIGITS = set("0123456789")


class CalcError(Exception):
    def __init__(self, code: int):
        super().__init__(f"Error {code}")
        self.code = code


def round_half_away(value: float, places: int) -> float:
    """Round half away from zero, matching the 12c display rule."""
    q = Decimal(1).scaleb(-places)
    dec = Decimal(str(value if math.isfinite(value) else 0))
    return float(dec.quantize(q, rounding=ROUND_HALF_UP))


def _finite(value: float) -> float:
    if not math.isfinite(value) or abs(value) > float(MAX_MAG):
        raise CalcError(0)
    if value != 0 and abs(value) < 1e-99:
        return 0.0
    return float(value)


def _near_int(value: float, tol: float = 1e-8) -> bool:
    return abs(value - round(value)) <= tol


def _trunc_int(value: float) -> int:
    return int(round(value))


# ---------------------------------------------------------------------------
# Time value of money
# ---------------------------------------------------------------------------

def tvm_residual(n, i_pct, pv, pmt, fv, begin: bool, compound_odd: bool) -> float:
    """Signed residual of the 12c compound-interest equation. Zero when balanced."""
    i = i_pct / 100.0
    if i <= -1.0:
        raise CalcError(5)
    fractional = abs(n - math.trunc(n)) > 1e-9
    if fractional:
        periods = float(math.trunc(n))
        frac = n - periods
        if compound_odd:
            factor = (1.0 + i) ** frac
        else:
            factor = 1.0 + frac * i
        pv_use = pv * factor
        n_use = periods
    else:
        pv_use = pv
        n_use = n
        factor = 1.0
    if abs(i) < 1e-14:
        return pv_use + pmt * n_use + fv
    growth = 1.0 + i
    annuity = (1.0 - growth ** (-n_use)) / i
    mode = 1.0 if begin else 0.0
    return pv_use + (1.0 + i * mode) * pmt * annuity + fv * (growth ** (-n_use))


def _annuity_parts(n_use, i, begin):
    if abs(i) < 1e-14:
        return n_use, 1.0, 1.0
    growth = 1.0 + i
    annuity = (1.0 - growth ** (-n_use)) / i
    mode = 1.0 if begin else 0.0
    return annuity, (1.0 + i * mode), growth


def solve_pv(n, i_pct, pmt, fv, begin, compound_odd) -> float:
    i = i_pct / 100.0
    if i <= -1.0:
        raise CalcError(5)
    fractional = abs(n - math.trunc(n)) > 1e-9
    if fractional:
        periods = float(math.trunc(n))
        frac = n - periods
        factor = (1.0 + i) ** frac if compound_odd else 1.0 + frac * i
        n_use = periods
    else:
        factor = 1.0
        n_use = n
    if abs(factor) < 1e-15:
        raise CalcError(5)
    annuity, mode_factor, growth = _annuity_parts(n_use, i, begin)
    if abs(i) < 1e-14:
        return -(pmt * n_use + fv) / factor
    fv_term = fv * (growth ** (-n_use))
    pmt_term = mode_factor * pmt * annuity
    return -(pmt_term + fv_term) / factor


def solve_pmt(n, i_pct, pv, fv, begin, compound_odd) -> float:
    if abs(n) < 1e-12:
        raise CalcError(5)
    i = i_pct / 100.0
    if i <= -1.0:
        raise CalcError(5)
    fractional = abs(n - math.trunc(n)) > 1e-9
    if fractional:
        periods = float(math.trunc(n))
        frac = n - periods
        factor = (1.0 + i) ** frac if compound_odd else 1.0 + frac * i
        pv_use = pv * factor
        n_use = periods
    else:
        pv_use = pv
        n_use = n
    annuity, mode_factor, growth = _annuity_parts(n_use, i, begin)
    denom = mode_factor * annuity
    if abs(denom) < 1e-15:
        raise CalcError(5)
    if abs(i) < 1e-14:
        return -(pv_use + fv) / n_use
    fv_term = fv * (growth ** (-n_use))
    return -(pv_use + fv_term) / denom


def solve_fv(n, i_pct, pv, pmt, begin, compound_odd) -> float:
    i = i_pct / 100.0
    if i <= -1.0:
        raise CalcError(5)
    fractional = abs(n - math.trunc(n)) > 1e-9
    if fractional:
        periods = float(math.trunc(n))
        frac = n - periods
        factor = (1.0 + i) ** frac if compound_odd else 1.0 + frac * i
        pv_use = pv * factor
        n_use = periods
    else:
        pv_use = pv
        n_use = n
    annuity, mode_factor, growth = _annuity_parts(n_use, i, begin)
    if abs(i) < 1e-14:
        return -(pv_use + pmt * n_use)
    return -(pv_use + mode_factor * pmt * annuity) * (growth ** n_use)


def solve_n(i_pct, pv, pmt, fv, begin) -> float:
    """Number of periods, then the 12c round-up rule."""
    i = i_pct / 100.0
    if i <= -1.0:
        raise CalcError(5)
    if abs(i) < 1e-14:
        if abs(pmt) < 1e-15:
            raise CalcError(5)
        raw = -(pv + fv) / pmt
    else:
        mode = 1.0 if begin else 0.0
        capital = (1.0 + i * mode) * pmt / i
        denom = fv - capital
        numer = -(pv + capital)
        if abs(denom) < 1e-15:
            raise CalcError(5)
        ratio = numer / denom
        if ratio <= 0 or (1.0 + i) <= 0:
            raise CalcError(5)
        raw = -math.log(ratio) / math.log(1.0 + i)
    if not math.isfinite(raw):
        raise CalcError(5)
    return _round_n(raw)


def _round_n(n: float) -> float:
    """Round n up to the next integer unless the fraction is under 0.005."""
    sign = -1.0 if n < 0 else 1.0
    mag = abs(n)
    frac = mag - math.floor(mag)
    if frac < 0.005:
        out = math.floor(mag + 1e-12)
    else:
        out = math.ceil(mag - 1e-12)
    return sign * float(out)


def _bisect(func, lo, hi, flo, fhi, steps=80):
    a, b = lo, hi
    fa, fb = flo, fhi
    for _ in range(steps):
        mid = (a + b) / 2.0
        try:
            fm = func(mid)
        except CalcError:
            return None
        if abs(fm) < 1e-9 or abs(b - a) < 1e-10:
            return mid
        if fa * fm <= 0:
            b, fb = mid, fm
        else:
            a, fa = mid, fm
    return (a + b) / 2.0


def find_root(func, seeds):
    """Find a root by scanning seeds for a sign change, then bisection."""
    samples = []
    for seed in seeds:
        try:
            samples.append((seed, func(seed)))
        except CalcError:
            continue
    samples.sort(key=lambda item: item[0])
    for value, fv in samples:
        if abs(fv) < 1e-7:
            return value
    for (a, fa), (b, fb) in zip(samples, samples[1:]):
        if fa * fb < 0:
            root = _bisect(func, a, b, fa, fb)
            if root is not None:
                return root
    return None


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def _shift_months(day: dt.date, months: int):
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    if day.day > last:
        return None
    return dt.date(year, month, day.day)


def _days_360(earlier: dt.date, later: dt.date) -> int:
    def f_start(d):
        z = 30 if d.day == 31 else d.day
        return 360 * d.year + 30 * d.month + z

    def f_end(d, start_day):
        if d.day == 31 and start_day >= 30:
            z = 30
        else:
            z = d.day
        return 360 * d.year + 30 * d.month + z

    return f_end(later, earlier.day) - f_start(earlier)


def bond_schedule(settle: dt.date, mature: dt.date):
    """Semiannual coupon window containing the settlement date."""
    if mature <= settle:
        raise CalcError(8)
    if (mature - settle).days > 500 * 366:
        raise CalcError(8)
    cursor = mature
    prev = None
    for _ in range(2000):
        prev = _shift_months(cursor, -6)
        if prev is None:
            raise CalcError(8)
        if prev <= settle:
            break
        cursor = prev
    else:
        raise CalcError(8)
    next_coupon = cursor
    count = 0
    walking = next_coupon
    while True:
        count += 1
        if walking == mature:
            break
        nxt = _shift_months(walking, 6)
        if nxt is None or nxt <= walking:
            raise CalcError(8)
        walking = nxt
        if count > 2000:
            raise CalcError(8)
    period_days = (next_coupon - prev).days
    if period_days <= 0:
        raise CalcError(8)
    accrued_days = (settle - prev).days
    to_next = (next_coupon - settle).days
    return {
        "prev": prev,
        "next": next_coupon,
        "n": count,
        "E": period_days,
        "DCS": accrued_days,
        "DSC": to_next,
        "DSM": (mature - settle).days,
    }


def bond_price(yield_pct, coupon_pct, settle, mature, redemption=100.0):
    """Actual/actual semiannual street price and accrued interest, per $100 par."""
    info = bond_schedule(settle, mature)
    semi = coupon_pct / 2.0
    yld = yield_pct / 200.0
    accrued = semi * (info["DCS"] / info["E"])
    if info["n"] <= 1:
        price = (redemption + semi) / (1.0 + yld * (info["DSM"] / info["E"])) - accrued
    else:
        w = info["DSC"] / info["E"]
        base = 1.0 + yld
        price = redemption / base ** (info["n"] - 1 + w)
        for k in range(1, info["n"] + 1):
            price += semi / base ** (k - 1 + w)
        price -= accrued
    return price, accrued


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class HP12C:
    """Interactive 12c machine. Feed faceplate key ids to :meth:`press`."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.t = 0.0
        self.lastx = 0.0
        self.n = 0.0
        self.i = 0.0
        self.pv = 0.0
        self.pmt = 0.0
        self.fv = 0.0
        self.regs = [0.0] * 20
        self.nj = [0] * 21
        self.begin = False
        self.compound_odd = False
        self.dmy = False
        self.euro = False
        self.fix = 2
        self.sci = False
        self.lift = True
        # When True, n/i/PV/PMT/FV store X. When False, they solve.
        self.pending_store = False
        self.entering = False
        self._buf = ""
        self._neg = False
        self._exp_mode = False
        self._exp_digits = ""
        self._exp_neg = False
        self.prefix = None
        self._sto_op = None
        self._gto_digits = ""
        self.program_mode = False
        self.program = [("gto", 0)] * 100
        self.alloc = 8
        self.pc = 0
        self.running = False
        self.error = None
        self.pr_error = False
        self.on = True
        self.mantissa_hold = False
        self.overlay = None
        self.date_dow = None
        self.payments_amortized = 0

    # -- persistence --------------------------------------------------------

    def to_dict(self):
        return {
            "x": self.x, "y": self.y, "z": self.z, "t": self.t, "lastx": self.lastx,
            "n": self.n, "i": self.i, "pv": self.pv, "pmt": self.pmt, "fv": self.fv,
            "regs": list(self.regs), "nj": list(self.nj),
            "begin": self.begin, "compound_odd": self.compound_odd, "dmy": self.dmy,
            "euro": self.euro, "fix": self.fix, "sci": self.sci,
            "program_mode": self.program_mode,
            "program": [list(step) for step in self.program],
            "alloc": self.alloc, "pc": self.pc,
            "payments_amortized": self.payments_amortized,
        }

    def load_dict(self, data):
        fresh = HP12C()
        self.__dict__.update(fresh.__dict__)
        for key in ("x", "y", "z", "t", "lastx", "n", "i", "pv", "pmt", "fv",
                    "begin", "compound_odd", "dmy", "euro", "fix", "sci",
                    "program_mode", "alloc", "pc", "payments_amortized"):
            if key in data:
                setattr(self, key, data[key])
        if "regs" in data:
            self.regs = [float(v) for v in data["regs"]]
        if "nj" in data:
            self.nj = [int(v) for v in data["nj"]]
        if "program" in data:
            self.program = [tuple(step) for step in data["program"]]
            while len(self.program) < 100:
                self.program.append(("gto", 0))

    def save(self, path: str):
        import json
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle)

    def load(self, path: str):
        import json
        with open(path, encoding="utf-8") as handle:
            self.load_dict(json.load(handle))

    # -- display ------------------------------------------------------------

    def reg_count(self) -> int:
        blocks = max(0, self.alloc - 8) // 7
        return 20 - blocks

    def annunciators(self) -> dict:
        prefix = self.prefix or ""
        return {
            "f": prefix == "f",
            "g": prefix in ("g", "rcl_g"),
            "BEGIN": self.begin,
            "D.MY": self.dmy,
            "C": self.compound_odd,
            "PRGM": self.program_mode,
            "hint": self._prefix_hint(),
            "run": self.running,
        }

    def _prefix_hint(self) -> str:
        if self.prefix == "f":
            return "f"
        if self.prefix == "g":
            return "g"
        if self.prefix == "sto_op" and self._sto_op:
            return "STO" + {"add": "+", "sub": "−", "mul": "×", "div": "÷"}[self._sto_op]
        if self.prefix in ("sto", "sto_dot"):
            return "STO ." if self.prefix == "sto_dot" else "STO"
        if self.prefix in ("rcl", "rcl_dot", "rcl_g"):
            return "RCL g" if self.prefix == "rcl_g" else ("RCL ." if self.prefix == "rcl_dot" else "RCL")
        if self.prefix in ("gto", "gto_pos"):
            dots = self._gto_digits
            label = "GTO ." if self.prefix == "gto_pos" else "GTO"
            return (label + " " + dots).strip()
        return ""

    def lcd(self) -> dict:
        """What the LCD should show: text, alignment, optional weekday digit."""
        blank = {"text": "", "align": "right", "dow": "", "off": True}
        if not self.on:
            return blank
        if self.pr_error:
            return {"text": "Pr Error", "align": "left", "dow": "", "off": False}
        if self.error is not None:
            return {"text": f"Error {self.error}", "align": "left", "dow": "", "off": False}
        if self.mantissa_hold:
            return {"text": self.mantissa_digits(), "align": "right", "dow": "", "off": False}
        if self.overlay:
            return {"text": self.overlay, "align": "left", "dow": "", "off": False}
        if self.program_mode:
            return {"text": self.format_line(self.pc), "align": "left", "dow": "", "off": False}
        if self.entering:
            return {"text": self.entry_text(), "align": "right", "dow": "", "off": False}
        dow = str(self.date_dow) if self.date_dow else ""
        return {"text": self.display(self.x), "align": "right", "dow": dow, "off": False}

    def display(self, value: float) -> str:
        """FIX/SCI formatting, except a complete calendar date keeps its year."""
        dated = self.format_date(value)
        if dated is not None:
            return dated
        return self.format_number(value)

    def entry_text(self) -> str:
        """Digits as keyed, so a date's year is not rounded off by FIX."""
        dec, _thou = self._sep()
        body = (self._buf or "0").replace(".", dec)
        if self._neg:
            body = "-" + body
        if self._exp_mode:
            digits = (self._exp_digits or "0").rjust(2)
            sign = "-" if self._exp_neg else " "
            body = f"{body}{sign}{digits}"
        return body

    def format_date(self, value: float) -> str | None:
        parts = self._date_parts(value)
        if parts is None:
            return None
        first, second, year = parts
        dec, _thou = self._sep()
        return f"{first}{dec}{second:02d}{year:04d}"

    def _date_parts(self, value: float):
        """Month/day encoding MM.DDYYYY or DD.MMYYYY, or None if it is not a date."""
        if not math.isfinite(value) or value <= 0 or value >= 100:
            return None
        scaled_f = value * 1_000_000
        scaled = int(round(scaled_f))
        if abs(scaled_f - scaled) > 1e-3:
            return None
        year = scaled % 10000
        if year < 1582 or year > 4046:
            return None
        rest = scaled // 10000
        second = rest % 100
        first = rest // 100
        if self.dmy:
            day, month = first, second
        else:
            month, day = first, second
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        try:
            dt.date(year, month, day)
        except ValueError:
            return None
        return first, second, year

    def format_number(self, value: float) -> str:
        if not math.isfinite(value):
            return "9.999999 99"
        if self.sci or (value != 0 and (abs(value) >= 1e10 or abs(value) < 1e-10)):
            return self._format_sci(value)
        return self._format_fix(value)

    def _sep(self):
        return (",", ".") if self.euro else (".", ",")

    def _format_fix(self, value: float) -> str:
        dec, thou = self._sep()
        places = self.fix
        rounded = round_half_away(value, places)
        if rounded != 0 and (abs(rounded) >= 1e10 or abs(value) >= 1e10):
            return self._format_sci(value)
        sign = "-" if rounded < 0 else ""
        mag = abs(rounded)
        int_digits = 1 if mag < 1 else len(str(int(math.floor(mag + 1e-9))))
        if int_digits > 10:
            return self._format_sci(value)
        use = min(places, max(0, 10 - int_digits))
        rounded = round_half_away(value, use)
        if rounded == 0:
            sign = ""
        text = f"{abs(rounded):.{use}f}"
        whole, _, frac = text.partition(".")
        groups = []
        while whole:
            groups.append(whole[-3:])
            whole = whole[:-3]
        whole = thou.join(reversed(groups))
        if use:
            return sign + whole + dec + frac
        return sign + whole

    def _format_sci(self, value: float) -> str:
        dec, _thou = self._sep()
        if value == 0:
            return f"0{dec}000000 00"
        sign = "-" if value < 0 else ""
        mag = abs(value)
        exp = int(math.floor(math.log10(mag)))
        mant = mag / 10 ** exp
        mant = round_half_away(mant, 6)
        if mant >= 10:
            mant /= 10.0
            exp += 1
        exp_sign = "-" if exp < 0 else " "
        body = f"{mant:.6f}".replace(".", dec)
        return f"{sign}{body}{exp_sign}{abs(exp):02d}"

    def mantissa_digits(self) -> str:
        value = self.x
        if value == 0 or not math.isfinite(value):
            return "0000000000"
        mag = abs(value)
        exp = math.floor(math.log10(mag))
        scaled = mag / 10 ** exp
        text = f"{scaled:.9f}".replace(".", "")
        return text[:10]

    def format_line(self, number: int) -> str:
        if number <= 0:
            return "00-"
        return f"{number:02d}-  {self.mnemonic(self.program[number])}"

    def mnemonic(self, action) -> str:
        kind = action[0]
        names = {
            "dot": ".", "chs": "CHS", "eex": "EEX", "enter": "ENTER", "clx": "CLx",
            "add": "+", "sub": "−", "mul": "×", "div": "÷", "pow": "yˣ",
            "rec": "1/x", "sqrt": "√x", "exp": "eˣ", "ln": "LN", "fact": "n!",
            "intg": "INTG", "frac": "FRAC", "rnd": "RND",
            "pct": "%", "chg": "Δ%", "tot": "%T",
            "roll": "R↓", "swap": "x↔y", "lstx": "LSTx",
            "amort": "AMORT", "simp": "INT", "npv": "NPV", "irr": "IRR",
            "price": "PRICE", "ytm": "YTM", "sl": "SL", "soyd": "SOYD", "db": "DB",
            "12x": "12×", "12div": "12÷", "cf0": "CFo", "cfj": "CFj", "nj": "Nj",
            "date": "DATE", "dys": "ΔDYS", "beg": "BEG", "end": "END",
            "sum": "Σ+", "sum-": "Σ−", "mean": "x̄", "s": "s", "wmean": "x̄w",
            "yhat": "ŷ,r", "xhat": "x̂,r",
            "rs": "R/S", "pse": "PSE", "le": "x≤y", "eq0": "x=0",
            "clr_sigma": "CL Σ", "clr_fin": "CL FIN",
        }
        if kind == "dig":
            return action[1]
        if kind == "fin":
            return {"n": "n", "i": "i", "pv": "PV", "pmt": "PMT", "fv": "FV"}[action[1]]
        if kind == "sto":
            return "STO " + _reg_name(action[1])
        if kind == "stoa":
            sym = {"add": "+", "sub": "−", "mul": "×", "div": "÷"}[action[1]]
            return f"STO{sym} {_reg_name(action[2])}"
        if kind == "rcl":
            return "RCL " + _reg_name(action[1])
        if kind == "rcl12":
            return "RCL 12×" if action[1] == "n" else "RCL 12÷"
        if kind == "rclf":
            return "RCL CFj" if action[1] == "cf" else "RCL Nj"
        if kind == "fix":
            return "SCI" if action[1] == "sci" else f"FIX {action[1]}"
        if kind == "gto":
            return f"GTO {action[1]:02d}"
        if kind in names:
            return names[kind]
        return kind

    # -- key entry ----------------------------------------------------------

    def press(self, key: str):
        """Handle one faceplate key. A key that clears an error is consumed."""
        if self.error is not None or self.pr_error:
            self.error = None
            self.pr_error = False
            self.overlay = None
            self.prefix = None
            return
        self.overlay = None
        self.mantissa_hold = False
        if key == "on":
            self.on = not self.on
            self.prefix = None
            self.running = False
            self.entering = False
            return
        if not self.on:
            return
        if self.running:
            self.running = False
            return
        action = self._resolve(key)
        if action is None:
            return
        if self.program_mode and not _immediate(action):
            self._store(action)
        else:
            self._exec(action)

    def release_mantissa(self):
        self.mantissa_hold = False

    def run(self, limit: int = 20000) -> int:
        """Run the stored program until it stops. Used by tests and R/S."""
        self.running = True
        steps = 0
        while self.running and steps < limit:
            status = self.step()
            steps += 1
            if status in ("stop", "error"):
                break
        if steps >= limit:
            self.running = False
        return steps

    def step(self) -> str:
        """Execute the next program line. Returns cont, pause, stop, or error."""
        if self.error is not None:
            self.running = False
            return "error"
        nxt = self.pc + 1
        if nxt < 1 or nxt > self.alloc or nxt > 99:
            self.pc = 0
            self.running = False
            return "stop"
        action = self.program[nxt]
        if action == ("gto", 0):
            self.pc = 0
            self.running = False
            return "stop"
        self.pc = nxt
        kind = action[0]
        if kind == "rs":
            self.running = False
            return "stop"
        if kind == "pse":
            return "pause"
        if kind == "gto":
            target = action[1]
            if target == 0:
                self.pc = 0
                self.running = False
                return "stop"
            if target > self.alloc or target > 99:
                self._fail(4)
                return "error"
            self.pc = target - 1
            return "cont"
        if kind in ("le", "eq0"):
            self._end_entry()
            passed = (self.x <= self.y) if kind == "le" else (self.x == 0)
            self.lift = True
            if not passed:
                self.pc += 1
            return "cont"
        self._exec(action)
        if self.error is not None:
            self.running = False
            return "error"
        return "cont"

    def _store(self, action):
        line = self.pc + 1
        try:
            self._ensure_alloc(line)
        except CalcError as err:
            self._fail(err.code)
            return
        if line > 99:
            self._fail(4)
            return
        self.program[line] = action
        self.pc = line

    def _ensure_alloc(self, line: int):
        while line > self.alloc:
            if self.alloc >= 99:
                raise CalcError(4)
            self.alloc = min(99, self.alloc + 7)

    # -- prefix resolver ----------------------------------------------------

    def _resolve(self, key: str):
        prefix = self.prefix
        if prefix in ("f", "g", "sto", "sto_dot", "sto_op", "rcl", "rcl_dot", "rcl_g", "gto", "gto_pos"):
            if key == "f" and prefix != "f":
                self._clear_prefix_state()
                self.prefix = "f"
                return None
            if key == "g" and prefix not in ("g", "rcl"):
                # RCL then g is the RCL-g prefix, handled below when prefix == rcl.
                if prefix != "rcl":
                    self._clear_prefix_state()
                    self.prefix = "g"
                    return None
        if prefix is None:
            if key == "f":
                self.prefix = "f"
                return None
            if key == "g":
                self.prefix = "g"
                return None
            if key == "sto":
                self.prefix = "sto"
                return None
            if key == "rcl":
                self.prefix = "rcl"
                return None
            return self._plain(key)
        if prefix == "f":
            return self._resolve_f(key)
        if prefix == "g":
            return self._resolve_g(key)
        if prefix == "sto":
            return self._resolve_sto(key)
        if prefix == "sto_dot":
            return self._resolve_dot_reg(key, "sto")
        if prefix == "sto_op":
            return self._resolve_sto_op(key)
        if prefix == "rcl":
            return self._resolve_rcl(key)
        if prefix == "rcl_dot":
            return self._resolve_dot_reg(key, "rcl")
        if prefix == "rcl_g":
            return self._resolve_rcl_g(key)
        if prefix in ("gto", "gto_pos"):
            return self._resolve_gto(key)
        self.prefix = None
        return None

    def _clear_prefix_state(self):
        self.prefix = None
        self._sto_op = None
        self._gto_digits = ""

    def _plain(self, key: str):
        if key in DIGITS:
            return ("dig", key)
        mapping = {
            "dot": ("dot",), "chs": ("chs",), "eex": ("eex",), "enter": ("enter",),
            "clx": ("clx",), "add": ("add",), "sub": ("sub",), "mul": ("mul",),
            "div": ("div",), "yx": ("pow",), "rec": ("rec",), "recip": ("rec",),
            "pct": ("pct",), "dpct": ("chg",), "chg": ("chg",), "pctt": ("tot",),
            "roll": ("roll",), "swap": ("swap",),
            "n": ("fin", "n"), "i": ("fin", "i"), "pv": ("fin", "pv"),
            "pmt": ("fin", "pmt"), "fv": ("fin", "fv"),
            "rs": ("rs",), "sst": ("sst",), "sum": ("sum",),
        }
        return mapping.get(key)

    def _resolve_f(self, key: str):
        self.prefix = None
        if key == "f":
            self.prefix = "f"
            return None
        if key == "g":
            self.prefix = "g"
            return None
        if key in DIGITS:
            return ("fix", int(key))
        if key == "dot":
            return ("fix", "sci")
        mapping = {
            "n": ("amort",), "i": ("simp",), "pv": ("npv",), "pmt": ("rnd",), "fv": ("irr",),
            "yx": ("price",), "rec": ("ytm",), "recip": ("ytm",),
            "pctt": ("sl",), "dpct": ("soyd",), "chg": ("soyd",), "pct": ("db",),
            "rs": ("pr",), "sst": ("clr_sigma",), "roll": ("clr_prgm",),
            "swap": ("clr_fin",), "clx": ("clr_reg",), "enter": ("clr_prefix",),
        }
        return mapping.get(key)

    def _resolve_g(self, key: str):
        self.prefix = None
        if key == "g":
            self.prefix = "g"
            return None
        if key == "f":
            self.prefix = "f"
            return None
        if key == "roll":
            self.prefix = "gto"
            self._gto_digits = ""
            return None
        mapping = {
            "n": ("12x",), "i": ("12div",), "pv": ("cf0",), "pmt": ("cfj",), "fv": ("nj",),
            "chs": ("date",), "7": ("beg",), "8": ("end",), "9": ("mem",),
            "yx": ("sqrt",), "rec": ("exp",), "recip": ("exp",),
            "pctt": ("ln",), "dpct": ("frac",), "chg": ("frac",), "pct": ("intg",),
            "eex": ("dys",), "4": ("dmy",), "5": ("mdy",), "6": ("wmean",),
            "rs": ("pse",), "sst": ("bst",), "swap": ("le",), "clx": ("eq0",),
            "enter": ("lstx",), "1": ("xhat",), "2": ("yhat",), "3": ("fact",),
            "0": ("mean",), "dot": ("s",), "sum": ("sum-",),
        }
        return mapping.get(key)

    def _resolve_sto(self, key: str):
        if key == "dot":
            self.prefix = "sto_dot"
            return None
        if key == "eex":
            self.prefix = None
            return ("compound",)
        if key in ("add", "sub", "mul", "div"):
            self.prefix = "sto_op"
            self._sto_op = key
            return None
        if key in DIGITS or key in ("n", "i", "pv", "pmt", "fv"):
            self.prefix = None
            return ("sto", int(key) if key in DIGITS else key)
        self.prefix = None
        return None

    def _resolve_dot_reg(self, key: str, which: str):
        self.prefix = None
        if key in DIGITS:
            return (which, 10 + int(key))
        return None

    def _resolve_sto_op(self, key: str):
        op = self._sto_op
        self.prefix = None
        self._sto_op = None
        if key in DIGITS:
            index = int(key)
            if index > 4:
                self._fail(4)
                return None
            return ("stoa", op, index)
        self._fail(4)
        return None

    def _resolve_rcl(self, key: str):
        if key == "dot":
            self.prefix = "rcl_dot"
            return None
        if key == "g":
            self.prefix = "rcl_g"
            return None
        if key in DIGITS or key in ("n", "i", "pv", "pmt", "fv"):
            self.prefix = None
            return ("rcl", int(key) if key in DIGITS else key)
        self.prefix = None
        return None

    def _resolve_rcl_g(self, key: str):
        self.prefix = None
        special = {"n": ("rcl12", "n"), "i": ("rcl12", "i"), "pmt": ("rclf", "cf"), "fv": ("rclf", "nj")}
        if key in special:
            return special[key]
        return self._resolve_g(key)

    def _resolve_gto(self, key: str):
        if key == "dot" and self.prefix == "gto" and not self._gto_digits:
            self.prefix = "gto_pos"
            return None
        if key in DIGITS:
            self._gto_digits += key
            if len(self._gto_digits) < 2:
                return None
            number = int(self._gto_digits)
            positioning = self.prefix == "gto_pos" or not self.program_mode
            self._clear_prefix_state()
            if positioning:
                return ("gto_pos", number)
            return ("gto", number)
        self._clear_prefix_state()
        self._fail(4)
        return None

    # -- execution ----------------------------------------------------------

    def _exec(self, action):
        self.date_dow = None
        kind = action[0]
        try:
            if kind == "dig":
                self._digit(action[1])
            elif kind == "dot":
                self._decimal()
            elif kind == "chs":
                self._chs()
            elif kind == "eex":
                self._eex()
            elif kind == "enter":
                self._enter()
            elif kind == "clx":
                self._clx()
            elif kind in ("add", "sub", "mul", "div", "pow"):
                self._binary(kind)
            elif kind in ("rec", "sqrt", "exp", "ln", "fact", "intg", "frac"):
                self._unary(kind)
            elif kind == "rnd":
                self._rnd()
            elif kind in ("pct", "chg", "tot"):
                self._percent(kind)
            elif kind == "roll":
                self._roll()
            elif kind == "swap":
                self._swap()
            elif kind == "lstx":
                self._lstx()
            elif kind == "fin":
                self._financial(action[1])
            elif kind == "fix":
                self._fix(action[1])
            elif kind == "sto":
                self._sto(action[1])
            elif kind == "stoa":
                self._sto_arith(action[1], action[2])
            elif kind == "rcl":
                self._rcl(action[1])
            elif kind == "rcl12":
                self._rcl12(action[1])
            elif kind == "rclf":
                self._rcl_flow(action[1])
            elif kind == "12x":
                self._twelve("mul")
            elif kind == "12div":
                self._twelve("div")
            elif kind == "amort":
                self._amort()
            elif kind == "simp":
                self._simple_interest()
            elif kind == "npv":
                self._npv()
            elif kind == "irr":
                self._irr()
            elif kind == "price":
                self._bond_price()
            elif kind == "ytm":
                self._bond_ytm()
            elif kind in ("sl", "soyd", "db"):
                self._depreciate(kind)
            elif kind == "cf0":
                self._cf0()
            elif kind == "cfj":
                self._cfj()
            elif kind == "nj":
                self._set_nj()
            elif kind == "date":
                self._date_add()
            elif kind == "dys":
                self._date_diff()
            elif kind == "beg":
                self._end_entry()
                self.begin = True
                self.lift = True
            elif kind == "end":
                self._end_entry()
                self.begin = False
                self.lift = True
            elif kind == "dmy":
                self.dmy = True
            elif kind == "mdy":
                self.dmy = False
            elif kind == "mem":
                self.overlay = f"P-{self.alloc:02d}  r-{self.reg_count():02d}"
            elif kind == "compound":
                self.compound_odd = not self.compound_odd
            elif kind == "sum":
                self._sigma(1)
            elif kind == "sum-":
                self._sigma(-1)
            elif kind == "mean":
                self._mean()
            elif kind == "s":
                self._stdev()
            elif kind == "wmean":
                self._wmean()
            elif kind == "yhat":
                self._linest("y")
            elif kind == "xhat":
                self._linest("x")
            elif kind == "rs":
                self.running = True
            elif kind == "pse":
                self._end_entry()
            elif kind in ("le", "eq0"):
                self._end_entry()
                self.lift = True
            elif kind == "pr":
                self._toggle_prgm()
            elif kind == "sst":
                self._sst()
            elif kind == "bst":
                self._bst()
            elif kind == "gto_pos":
                self._goto(action[1])
            elif kind == "clr_sigma":
                self._clear_sigma()
            elif kind == "clr_fin":
                self._clear_fin()
            elif kind == "clr_reg":
                self._clear_reg()
            elif kind == "clr_prgm":
                self._clear_prgm()
            elif kind == "clr_prefix":
                self._clear_prefix_state()
                self.mantissa_hold = True
        except CalcError as err:
            self._fail(err.code)

    def _fail(self, code: int):
        self.error = code
        self.entering = False
        self.prefix = None
        self._sto_op = None
        self._gto_digits = ""
        self.running = False
        self.lift = True

    def _end_entry(self):
        if self.entering:
            self._sync_entry()
            self.entering = False

    def _digit(self, digit: str):
        self._start_entry()
        self.pending_store = True
        if self._exp_mode:
            if len(self._exp_digits) < 2:
                self._exp_digits += digit
        else:
            mantissa = self._buf.replace(".", "")
            if len(mantissa) < 10:
                self._buf += digit
        self._sync_entry()

    def _decimal(self):
        self._start_entry()
        self.pending_store = True
        if self._exp_mode:
            return
        if "." not in self._buf:
            self._buf = (self._buf or "0") + "."
        self._sync_entry()

    def _start_entry(self):
        if self.entering:
            return
        if self.lift:
            self._stack_lift()
        self.entering = True
        self._buf = ""
        self._neg = False
        self._exp_mode = False
        self._exp_digits = ""
        self._exp_neg = False
        self.lift = False
        self.date_dow = None

    def _sync_entry(self):
        text = self._buf
        if text in ("", "."):
            mant = 0.0
        else:
            mant = float(text)
        if self._neg:
            mant = -abs(mant)
        if self._exp_mode and self._exp_digits:
            exp = int(self._exp_digits)
            if self._exp_neg:
                exp = -exp
            mant *= 10.0 ** exp
        self.x = mant

    def _chs(self):
        if self.entering:
            if self._exp_mode:
                self._exp_neg = not self._exp_neg
            else:
                self._neg = not self._neg
            self._sync_entry()
        else:
            self.x = -self.x if self.x != 0 else 0.0
        self.pending_store = True

    def _eex(self):
        if not self.entering:
            self._start_entry()
            self._buf = "1"
        if not self._exp_mode:
            self._exp_mode = True
            self._exp_digits = ""
            self._exp_neg = False
        self.pending_store = True
        self._sync_entry()

    def _enter(self):
        self._end_entry()
        self._stack_lift()
        self.lift = False
        self.pending_store = True

    def _clx(self):
        self.entering = False
        self.x = 0.0
        self.lift = False
        self.pending_store = True

    def _stack_lift(self):
        self.t = self.z
        self.z = self.y
        self.y = self.x

    def _binary(self, kind: str):
        self._end_entry()
        x, y = self.x, self.y
        try:
            if kind == "add":
                result = y + x
            elif kind == "sub":
                result = y - x
            elif kind == "mul":
                result = y * x
            elif kind == "div":
                if x == 0:
                    raise CalcError(0)
                result = y / x
            else:
                result = _power(y, x)
            result = _finite(result)
        except CalcError:
            self.lastx = x
            raise
        self.lastx = x
        self.x = result
        self.y = self.z
        self.z = self.t
        self.lift = True
        self.pending_store = True

    def _unary(self, kind: str):
        self._end_entry()
        old = self.x
        try:
            result = _finite(_unary_value(kind, old))
        except CalcError:
            self.lastx = old
            raise
        self.lastx = old
        self.x = result
        self.lift = True
        self.pending_store = True

    def _rnd(self):
        self._end_entry()
        self.lastx = self.x
        self.x = self._round_internal(self.x)
        self.lift = True
        self.pending_store = True

    def _round_internal(self, value: float) -> float:
        if self.sci or (value != 0 and (abs(value) >= 1e10 or abs(value) < 1e-10)):
            if value == 0:
                return 0.0
            exp = math.floor(math.log10(abs(value)))
            mant = round_half_away(abs(value) / 10 ** exp, 6)
            if mant >= 10:
                mant /= 10
                exp += 1
            signed = -mant if value < 0 else mant
            return signed * 10 ** exp
        mag = abs(value)
        int_digits = 1 if mag < 1 else len(str(int(math.floor(mag + 1e-9))))
        places = self.fix if int_digits > 10 else min(self.fix, max(0, 10 - int_digits))
        return round_half_away(value, places)

    def _percent(self, kind: str):
        self._end_entry()
        x, y = self.x, self.y
        if kind == "pct":
            result = y * x / 100.0
        elif y == 0:
            self.lastx = x
            raise CalcError(0)
        elif kind == "chg":
            result = (x - y) / y * 100.0
        else:
            result = x / y * 100.0
        self.lastx = x
        self.x = _finite(result)
        self.lift = True
        self.pending_store = True

    def _roll(self):
        self._end_entry()
        x, y, z, t = self.x, self.y, self.z, self.t
        self.x, self.y, self.z, self.t = y, z, t, x
        self.lift = True
        self.pending_store = True

    def _swap(self):
        self._end_entry()
        self.x, self.y = self.y, self.x
        self.lift = True
        self.pending_store = True

    def _lstx(self):
        self._end_entry()
        if self.lift:
            self._stack_lift()
        self.x = self.lastx
        self.lift = True
        self.pending_store = True

    def _recall_value(self, value: float):
        self._end_entry()
        if self.lift:
            self._stack_lift()
        self.x = value
        self.lift = True
        self.pending_store = True
        self.entering = False

    def _financial(self, name: str):
        self._end_entry()
        if self.pending_store:
            setattr(self, name, self.x)
            self.pending_store = False
            self.lift = True
            self.payments_amortized = 0
            return
        self._solve(name)

    def _solve(self, name: str):
        self.lastx = self.x
        try:
            if name == "n":
                result = solve_n(self.i, self.pv, self.pmt, self.fv, self.begin)
            elif name == "i":
                result = self._solve_interest()
            elif name == "pv":
                if self.i <= -100:
                    raise CalcError(5)
                result = solve_pv(self.n, self.i, self.pmt, self.fv, self.begin, self.compound_odd)
            elif name == "pmt":
                if self.i <= -100:
                    raise CalcError(5)
                result = solve_pmt(self.n, self.i, self.pv, self.fv, self.begin, self.compound_odd)
            else:
                if self.i <= -100:
                    raise CalcError(5)
                result = solve_fv(self.n, self.i, self.pv, self.pmt, self.begin, self.compound_odd)
            result = _finite(result)
        except CalcError:
            raise
        setattr(self, name, result)
        self.x = result
        self.pending_store = False
        self.lift = True
        self.payments_amortized = 0

    def _solve_interest(self) -> float:
        def residual(rate):
            return tvm_residual(self.n, rate, self.pv, self.pmt, self.fv, self.begin, self.compound_odd)

        seeds = [self.i, 0.0, 0.5, 1, 2, 5, 10, 12, -1, -5, 20, 50, 100, -20, 0.1, 8]
        # A denser scan catches awkward cash-flow shapes without much cost.
        seeds.extend(range(-80, 201, 5))
        root = find_root(residual, seeds)
        if root is None:
            raise CalcError(5)
        return root

    def _fix(self, mode):
        self._end_entry()
        if mode == "sci":
            self.sci = True
        else:
            self.sci = False
            self.fix = int(mode)
        self.lift = True

    def _reg_ok(self, index: int) -> bool:
        return 0 <= index < self.reg_count()

    def _sto(self, target):
        self._end_entry()
        if isinstance(target, str):
            setattr(self, target, self.x)
            self.payments_amortized = 0
        else:
            if not self._reg_ok(target):
                raise CalcError(6)
            self.regs[target] = self.x
        self.pending_store = False
        self.lift = True

    def _sto_arith(self, op: str, index: int):
        self._end_entry()
        if index > 4 or not self._reg_ok(index):
            raise CalcError(4)
        current = self.regs[index]
        if op == "add":
            result = current + self.x
        elif op == "sub":
            result = current - self.x
        elif op == "mul":
            result = current * self.x
        else:
            if self.x == 0:
                raise CalcError(0)
            result = current / self.x
        if not math.isfinite(result) or abs(result) > float(MAX_MAG):
            raise CalcError(1)
        self.regs[index] = result
        self.lift = True

    def _rcl(self, target):
        if isinstance(target, str):
            value = getattr(self, target)
        else:
            if not self._reg_ok(target):
                raise CalcError(6)
            value = self.regs[target]
        self._recall_value(value)

    def _rcl12(self, which: str):
        if which == "n":
            self._recall_value(self.n / 12.0)
        else:
            self._recall_value(self.i * 12.0)

    def _twelve(self, which: str):
        self._end_entry()
        self.lastx = self.x
        if which == "mul":
            self.x = _finite(self.x * 12.0)
            self.n = self.x
        else:
            self.x = _finite(self.x / 12.0)
            self.i = self.x
        self.pending_store = False
        self.lift = True
        self.payments_amortized = 0

    def _places(self) -> int:
        return 6 if self.sci else self.fix

    def _amort(self):
        self._end_entry()
        count = self.x
        if count <= 0 or not _near_int(count):
            raise CalcError(5)
        if self.i <= -100:
            raise CalcError(5)
        count = int(round(count))
        places = self._places()
        rate = self.i / 100.0
        balance = self.pv
        payment = self.pmt
        interest_sum = 0.0
        principal_sum = 0.0
        for _ in range(count):
            zero_interest = self.begin and self.payments_amortized == 0
            if zero_interest:
                interest = 0.0
            else:
                raw = abs(balance * rate)
                interest = round_half_away(raw, places)
                if payment < 0:
                    interest = -interest
                elif payment == 0:
                    interest = 0.0
            principal = payment - interest
            balance = balance + principal
            interest_sum += interest
            principal_sum += principal
            self.payments_amortized += 1
        self.lastx = self.x
        self.t = self.z
        self.z = float(count)
        self.y = principal_sum
        self.x = interest_sum
        self.pv = balance
        self.n = float(self.payments_amortized)
        self.pending_store = False
        self.lift = True

    def _simple_interest(self):
        self._end_entry()
        rate = self.i / 100.0
        self.lastx = self.x
        self.y = _finite(self.n * rate * self.pv / 365.0)
        self.x = _finite(self.n * rate * self.pv / 360.0)
        self.lift = True
        self.pending_store = True

    def _cf_get(self, index: int) -> float:
        if index == 20:
            return self.fv
        if not self._reg_ok(index):
            raise CalcError(6)
        return self.regs[index]

    def _cf_set(self, index: int, value: float):
        if index == 20:
            self.fv = value
            return
        if not self._reg_ok(index):
            raise CalcError(6)
        self.regs[index] = value

    def _flow_index(self) -> int:
        if not _near_int(self.n) or self.n < -1e-9 or self.n > 20:
            raise CalcError(6)
        return int(round(self.n))

    def _cf0(self):
        self._end_entry()
        self._cf_set(0, self.x)
        self.nj[0] = 1
        self.n = 0.0
        self.pending_store = False
        self.lift = True

    def _cfj(self):
        self._end_entry()
        current = self._flow_index()
        nxt = current + 1
        if nxt > 20:
            raise CalcError(6)
        self._cf_set(nxt, self.x)
        self.nj[nxt] = 1
        self.n = float(nxt)
        self.pending_store = False
        self.lift = True

    def _set_nj(self):
        self._end_entry()
        if self.x < 0 or self.x > 99 or not _near_int(self.x):
            raise CalcError(6)
        index = self._flow_index()
        self.nj[index] = int(round(self.x))
        self.lift = True
        self.pending_store = False

    def _npv_of(self, i_pct: float) -> float:
        rate = i_pct / 100.0
        if rate <= -1.0:
            raise CalcError(5)
        groups = self._flow_index()
        total = 0.0
        period = 0
        for group in range(groups + 1):
            amount = self._cf_get(group)
            times = self.nj[group] if self.nj[group] else 1
            for _ in range(times):
                if abs(rate) < 1e-15:
                    total += amount
                else:
                    total += amount / (1.0 + rate) ** period
                period += 1
        return total

    def _npv(self):
        self._end_entry()
        if self.i <= -100:
            raise CalcError(5)
        value = _finite(self._npv_of(self.i))
        self.lastx = self.x
        self.x = value
        self.lift = True
        self.pending_store = True

    def _expanded_signs(self):
        groups = self._flow_index()
        positive = negative = False
        for group in range(groups + 1):
            amount = self._cf_get(group)
            times = self.nj[group] if self.nj[group] else 1
            if times <= 0 or amount == 0:
                continue
            if amount > 0:
                positive = True
            else:
                negative = True
        return positive, negative

    def _irr(self):
        self._end_entry()
        positive, negative = self._expanded_signs()
        if not positive or not negative:
            raise CalcError(7)

        def residual(rate):
            return self._npv_of(rate)

        seeds = [self.i, 0.0, 5, 10, 15, 20, -10, 30, 50, 100, 1, -5, 8, 12, 25]
        seeds.extend(range(-40, 150, 5))
        root = find_root(residual, seeds)
        if root is None or abs(residual(root)) > 1e-4:
            raise CalcError(3)
        self.lastx = self.x
        self.i = root
        self.x = root
        self.pending_store = False
        self.lift = True

    def _rcl_flow(self, which: str):
        index = self._flow_index()
        if which == "nj":
            self._recall_value(float(self.nj[index] if self.nj[index] else 1))
            return
        value = self._cf_get(index)
        self._recall_value(value)
        if index > 0:
            self.n = float(index - 1)

    def _read_dates(self):
        self._end_entry()
        later = _decode_date(self.x, self.dmy)
        earlier = _decode_date(self.y, self.dmy)
        return earlier, later

    def _date_diff(self):
        earlier, later = self._read_dates()
        actual = float((later - earlier).days)
        basis = float(_days_360(earlier, later))
        self.lastx = self.x
        self.y = basis
        self.x = actual
        self.lift = True
        self.pending_store = True

    def _date_add(self):
        self._end_entry()
        start = _decode_date(self.y, self.dmy)
        if not _near_int(self.x):
            raise CalcError(8)
        days = int(round(self.x))
        try:
            result = start + dt.timedelta(days=days)
        except OverflowError as err:
            raise CalcError(8) from err
        if result.year < 1582 or result.year > 4046:
            raise CalcError(8)
        self.lastx = self.x
        self.x = _encode_date(result, self.dmy)
        self.date_dow = result.weekday() + 1
        self.lift = True
        self.pending_store = True

    def _bond_inputs(self):
        self._end_entry()
        mature = _decode_date(self.x, self.dmy)
        settle = _decode_date(self.y, self.dmy)
        return settle, mature

    def _bond_price(self):
        settle, mature = self._bond_inputs()
        price, accrued = bond_price(self.i, self.pmt, settle, mature)
        self.lastx = self.x
        self.y = _finite(accrued)
        self.x = _finite(price)
        self.pv = self.x
        self.pending_store = False
        self.lift = True
        self.payments_amortized = 0

    def _bond_ytm(self):
        settle, mature = self._bond_inputs()
        target = self.pv
        coupon = self.pmt

        def gap(rate):
            price, _accrued = bond_price(rate, coupon, settle, mature)
            return price - target

        seeds = [self.i, 0, 1, 3, 5, 8, 10, 15, 20, 30, 50, 100, -5, 7, 9]
        seeds.extend(range(0, 80, 2))
        root = find_root(gap, seeds)
        if root is None:
            raise CalcError(5)
        self.lastx = self.x
        self.i = root
        self.x = root
        self.pending_store = False
        self.lift = True

    def _depreciate(self, method: str):
        self._end_entry()
        if self.x <= 0 or not _near_int(self.x) or self.n <= 0 or self.n > 1e10:
            raise CalcError(5)
        year = int(round(self.x))
        life = self.n
        cost = self.pv
        salvage = self.fv
        base = cost - salvage
        if method == "sl":
            dpn = base / life
            remaining = base - dpn * year
        elif method == "soyd":
            soyd = life * (life + 1) / 2.0
            if soyd == 0:
                raise CalcError(5)
            dpn = base * (life - year + 1) / soyd
            used = sum(base * (life - j + 1) / soyd for j in range(1, year + 1))
            remaining = base - used
        else:
            factor = self.i / 100.0
            book = cost
            used = 0.0
            dpn = 0.0
            for _j in range(year):
                dpn = book * factor / life
                room = book - salvage
                if dpn > room:
                    dpn = room
                if dpn < 0:
                    dpn = 0.0
                book -= dpn
                used += dpn
            remaining = book - salvage
        self.lastx = self.x
        self.y = _finite(remaining)
        self.x = _finite(dpn)
        self.lift = True
        self.pending_store = True

    def _sigma(self, sign: int):
        self._end_entry()
        x, y = self.x, self.y
        self.lastx = x
        self.regs[1] += sign
        self.regs[2] += sign * x
        self.regs[3] += sign * x * x
        self.regs[4] += sign * y
        self.regs[5] += sign * y * y
        self.regs[6] += sign * x * y
        self.x = self.regs[1]
        self.lift = False
        self.pending_store = False

    def _stats(self):
        count = self.regs[1]
        return count, self.regs[2], self.regs[3], self.regs[4], self.regs[5], self.regs[6]

    def _mean(self):
        self._end_entry()
        count, sx, _sx2, sy, _sy2, _sxy = self._stats()
        if count == 0:
            raise CalcError(2)
        self.lastx = self.x
        self.y = sy / count
        self.x = sx / count
        self.lift = True
        self.pending_store = True

    def _stdev(self):
        self._end_entry()
        count, sx, sx2, sy, sy2, _sxy = self._stats()
        if count == 0 or count == 1:
            raise CalcError(2)
        var_x = (count * sx2 - sx * sx) / (count * (count - 1))
        var_y = (count * sy2 - sy * sy) / (count * (count - 1))
        if var_x < -1e-8 or var_y < -1e-8:
            raise CalcError(2)
        self.lastx = self.x
        self.y = math.sqrt(max(0.0, var_y))
        self.x = math.sqrt(max(0.0, var_x))
        self.lift = True
        self.pending_store = True

    def _wmean(self):
        self._end_entry()
        _count, sx, _sx2, _sy, _sy2, sxy = self._stats()
        if sx == 0:
            raise CalcError(2)
        self.lastx = self.x
        self.x = sxy / sx
        self.lift = True
        self.pending_store = True

    def _regression(self):
        count, sx, sx2, sy, sy2, sxy = self._stats()
        if count == 0:
            raise CalcError(2)
        den_x = count * sx2 - sx * sx
        den_y = count * sy2 - sy * sy
        if den_x <= 1e-9 or den_y <= 1e-9:
            raise CalcError(2)
        slope = (count * sxy - sx * sy) / den_x
        intercept = (sy / count) - slope * (sx / count)
        corr = (count * sxy - sx * sy) / math.sqrt(den_x * den_y)
        return slope, intercept, corr

    def _linest(self, which: str):
        self._end_entry()
        slope, intercept, corr = self._regression()
        given = self.x
        if which == "y":
            estimate = intercept + slope * given
        else:
            if abs(slope) < 1e-15:
                raise CalcError(2)
            estimate = (given - intercept) / slope
        self.lastx = given
        self.y = corr
        self.x = _finite(estimate)
        self.lift = True
        self.pending_store = True

    def _clear_sigma(self):
        for index in range(1, 7):
            self.regs[index] = 0.0
        self.x = self.y = self.z = self.t = 0.0
        self.entering = False
        self.lift = True
        self.pending_store = False

    def _clear_fin(self):
        self.n = self.i = self.pv = self.pmt = self.fv = 0.0
        self.payments_amortized = 0
        self.lift = True

    def _clear_reg(self):
        self.regs = [0.0] * 20
        self.nj = [0] * 21
        self._clear_fin()
        self.x = self.y = self.z = self.t = self.lastx = 0.0
        self.entering = False
        self.pending_store = False
        self.lift = True

    def _clear_prgm(self):
        if self.program_mode:
            self.program = [("gto", 0)] * 100
            self.alloc = 8
        self.pc = 0

    def _toggle_prgm(self):
        self.program_mode = not self.program_mode
        self.entering = False
        self._clear_prefix_state()
        if not self.program_mode:
            self.pc = 0

    def _sst(self):
        if self.program_mode:
            if self.pc < self.alloc:
                self.pc += 1
            return
        self.step()

    def _bst(self):
        if self.program_mode:
            if self.pc > 0:
                self.pc -= 1
            return
        self.overlay = self.format_line(max(0, self.pc - 1))

    def _goto(self, line: int):
        if line != 0 and (line > self.alloc or line > 99):
            raise CalcError(4)
        self.pc = line


def _reg_name(target) -> str:
    if isinstance(target, str):
        return {"n": "n", "i": "i", "pv": "PV", "pmt": "PMT", "fv": "FV"}[target]
    if target >= 10:
        return f".{target - 10}"
    return str(target)


def _immediate(action) -> bool:
    return action[0] in {
        "pr", "sst", "bst", "clr_prefix", "clr_prgm", "clr_reg",
        "gto_pos", "dmy", "mdy", "mem", "compound",
    }


def _power(y, x):
    if y == 0 and x <= 0:
        raise CalcError(0)
    if y < 0 and not _near_int(x):
        raise CalcError(0)
    return y ** x


def _unary_value(kind: str, value: float) -> float:
    if kind == "rec":
        if value == 0:
            raise CalcError(0)
        return 1.0 / value
    if kind == "sqrt":
        if value < 0:
            raise CalcError(0)
        return math.sqrt(value)
    if kind == "exp":
        return math.exp(value)
    if kind == "ln":
        if value <= 0:
            raise CalcError(0)
        return math.log(value)
    if kind == "fact":
        if value < 0 or not _near_int(value):
            raise CalcError(0)
        n = int(round(value))
        if n > 69:
            raise CalcError(0)
        result = 1
        for k in range(2, n + 1):
            result *= k
        return float(result)
    if kind == "intg":
        return float(math.trunc(value))
    if kind == "frac":
        return value - math.trunc(value)
    raise CalcError(0)


def _encode_date(day: dt.date, dmy: bool) -> float:
    if dmy:
        scaled = day.day * 1_000_000 + day.month * 10_000 + day.year
    else:
        scaled = day.month * 1_000_000 + day.day * 10_000 + day.year
    return scaled / 1_000_000


def _decode_date(value: float, dmy: bool) -> dt.date:
    if not math.isfinite(value):
        raise CalcError(8)
    scaled = int(round(abs(value) * 1_000_000))
    year = scaled % 10000
    scaled //= 10000
    second = scaled % 100
    first = scaled // 100
    if dmy:
        day, month = first, second
    else:
        month, day = first, second
    if year < 1582 or year > 4046:
        raise CalcError(8)
    try:
        return dt.date(year, month, day)
    except ValueError as err:
        raise CalcError(8) from err
