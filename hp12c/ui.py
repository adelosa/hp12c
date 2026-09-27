"""GTK 4 faceplate styled on the classic HP 12c."""

from __future__ import annotations

import json
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from hp12c.engine import HP12C

APP_ID = "org.local.TwelveC"

CSS = """
.twelve-window { background: #0c0d10; }
.case {
  background: #1c1e22;
  border-radius: 18px;
  border: 1px solid #3c4048;
  padding: 14px 16px 18px 16px;
}
.brand {
  font-family: "DejaVu Serif", serif;
  font-style: italic;
  font-weight: 700;
  font-size: 34px;
  color: #f0d48a;
}
.brand-sub {
  color: #8d929c;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.4px;
}
button.help-link {
  background-color: #24262c;
  background-image: none;
  color: #e6b84e;
  border: 1px solid #a6843a;
  border-radius: 6px;
  box-shadow: none;
  padding: 2px 14px;
  min-height: 28px;
  font-size: 13px;
  font-weight: 700;
}
button.help-link:hover {
  background-color: #34322a;
}
button.help-link label {
  color: #e6b84e;
}
.bezel {
  background: linear-gradient(to bottom, #f3ead0, #b7aa86);
  border-radius: 12px;
  padding: 7px;
}
.lcd {
  background: #c5c8a8;
  border-radius: 5px;
  padding: 6px 12px 2px 12px;
}
.digits {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 42px;
  font-weight: 700;
  color: #1a1c12;
}
.dow {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 28px;
  font-weight: 700;
  color: #1a1c12;
}
.ann {
  font-size: 12px;
  font-weight: 800;
  color: #1a1c12;
  margin-right: 10px;
}
.hint {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 12px;
  font-weight: 700;
  color: #1a1c12;
}
.plate {
  background: #121318;
  border-radius: 6px;
  padding: 6px 10px;
}
.plate-text {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 12px;
  color: #e0c27a;
}
.gold-lab {
  font-family: "DejaVu Sans", sans-serif;
  color: #e6b84e;
  font-size: 11px;
  font-weight: 800;
}
.bracket {
  border-top: 1px solid #e6b84e;
  border-left: 1px solid #e6b84e;
  border-right: 1px solid #e6b84e;
  border-radius: 7px 7px 0 0;
  margin: 2px 3px 0 3px;
  padding-top: 1px;
}
.bracket-title {
  font-family: "DejaVu Sans", sans-serif;
  color: #e6b84e;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.6px;
}
.blue-lab {
  font-family: "DejaVu Sans", sans-serif;
  color: #9ecbff;
  font-size: 11px;
  font-weight: 700;
}
.prim-lab {
  font-family: "DejaVu Sans", sans-serif;
  color: #f7f7f7;
  font-size: 16px;
  font-weight: 800;
}
.calc-key {
  background: #2b2e33;
  border-radius: 6px;
  border: 1px solid #0b0c0e;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
  padding: 2px 2px 4px 2px;
  min-height: 52px;
  min-width: 62px;
}
.calc-key:hover { background: #3a3e45; }
.calc-key:active { background: #191b1f; }
.fkey {
  background: linear-gradient(to bottom, #f0d078, #c4982a);
  border-color: #6d5410;
}
.fkey:hover { background: #e2c15a; }
.gkey {
  background: linear-gradient(to bottom, #4b92d4, #1e568f);
  border-color: #163e68;
}
.gkey:hover { background: #3d86c8; }
.enter-key { min-height: 108px; }
.fkey .prim-lab { color: #241a06; font-size: 24px; }
.gkey .prim-lab { color: white; font-size: 24px; }
.enter-key .prim-lab { font-size: 15px; letter-spacing: 1px; }
"""

# id, face label, gold f label, blue g label, extra css class
ROWS = [
    [
        ("n", "n", "AMORT", "12×", ""),
        ("i", "i", "INT", "12÷", ""),
        ("pv", "PV", "NPV", "CFo", ""),
        ("pmt", "PMT", "RND", "CFj", ""),
        ("fv", "FV", "IRR", "Nj", ""),
        ("chs", "CHS", "", "DATE", ""),
        ("7", "7", "", "BEG", ""),
        ("8", "8", "", "END", ""),
        ("9", "9", "", "MEM", ""),
        ("div", "÷", "", "", ""),
    ],
    [
        ("yx", "yˣ", "PRICE", "√x", ""),
        ("rec", "1/x", "YTM", "eˣ", ""),
        ("pctt", "%T", "SL", "LN", ""),
        ("dpct", "Δ%", "SOYD", "FRAC", ""),
        ("pct", "%", "DB", "INTG", ""),
        ("eex", "EEX", "", "ΔDYS", ""),
        ("4", "4", "", "D.MY", ""),
        ("5", "5", "", "M.DY", ""),
        ("6", "6", "", "x̄w", ""),
        ("mul", "×", "", "", ""),
    ],
    [
        ("rs", "R/S", "P/R", "PSE", ""),
        ("sst", "SST", "Σ", "BST", ""),
        ("roll", "R↓", "PRGM", "GTO", ""),
        ("swap", "x↔y", "FIN", "x≤y", ""),
        ("clx", "CLx", "REG", "x=0", ""),
        None,  # ENTER lives here and spans the next row
        ("1", "1", "", "x̂,r", ""),
        ("2", "2", "", "ŷ,r", ""),
        ("3", "3", "", "n!", ""),
        ("sub", "−", "", "", ""),
    ],
    [
        ("on", "ON", "", "", ""),
        ("f", "f", "", "", "fkey"),
        ("g", "g", "", "", "gkey"),
        ("sto", "STO", "", "", ""),
        ("rcl", "RCL", "", "", ""),
        None,
        ("0", "0", "", "x̄", ""),
        ("dot", "·", "", "s", ""),
        ("sum", "Σ+", "", "Σ−", ""),
        ("add", "+", "", "", ""),
    ],
]

TIPS = {
    "n": "Store or compute the number of periods.\nGold f: AMORT. Blue g: multiply by 12 and store in n.",
    "i": "Store or compute the periodic interest rate.\nGold f: simple interest. Blue g: divide by 12 and store in i.",
    "pv": "Store or compute present value.\nGold f: NPV. Blue g: initial cash flow CFo.",
    "pmt": "Store or compute the payment.\nGold f: round X to the display. Blue g: next cash flow CFj.",
    "fv": "Store or compute future value.\nGold f: IRR. Blue g: cash-flow repeat count Nj.",
    "chs": "Change sign. Blue g: DATE, add days in X to the date in Y.",
    "yx": "Raise Y to the power X.\nGold f: bond PRICE. Blue g: square root.",
    "rec": "Reciprocal.\nGold f: bond YTM. Blue g: eˣ.",
    "pctt": "Percent of total, X is what percent of Y.\nGold f: straight-line depreciation. Blue g: LN.",
    "dpct": "Percent change from Y to X.\nGold f: sum-of-the-years-digits. Blue g: fractional part.",
    "pct": "X percent of Y. Y stays put, so + adds the percent back on.\nGold f: declining-balance depreciation. Blue g: integer part.",
    "eex": "Enter an exponent of 10. Blue g: days between the dates in Y and X.",
    "rs": "Run or stop a program.\nGold f: switch program/run mode. Blue g: pause.",
    "sst": "Single step.\nGold f: clear statistics. Blue g: step back in the program.",
    "roll": "Roll the stack down.\nGold f: clear the program. Blue g: GTO, then two digits.",
    "swap": "Swap X and Y.\nGold f: clear the financial registers. Blue g: test x≤y.",
    "clx": "Clear X.\nGold f: clear registers. Blue g: test x=0.",
    "enter": "Enter. Copies X into Y and drops stack-lift.\nGold f: cancel a prefix and show all 10 digits. Blue g: LAST X.",
    "on": "Blank the display. Continuous memory is kept. Press again to wake.",
    "f": "Gold prefix. Then a digit sets the number of decimal places. f · is scientific notation.",
    "g": "Blue prefix.",
    "sto": "Store X. Then 0–9, · 0–9, or n i PV PMT FV.\nSTO + − × ÷ then 0–4 does register arithmetic.\nSTO EEX toggles compound interest for an odd period.",
    "rcl": "Recall. Same register addresses as STO.\nRCL g 12× recalls n÷12. RCL g 12÷ recalls i×12.\nRCL g CFj reviews cash flows from the end.",
    "sum": "Add the X,Y pair to the statistics registers.\nBlue g: subtract a pair.",
    "0": "Digit. Blue g: mean of the statistics. Gold f: FIX 0.",
    "1": "Digit. Blue g: estimate x from y, and the correlation.",
    "2": "Digit. Blue g: estimate y from x, and the correlation.",
    "3": "Digit. Blue g: factorial.",
    "4": "Digit. Blue g: day.month.year dates.",
    "5": "Digit. Blue g: month.day.year dates.",
    "6": "Digit. Blue g: weighted mean. X values are the weights.",
    "7": "Digit. Blue g: payments at the beginning of the period.",
    "8": "Digit. Blue g: payments at the end of the period.",
    "9": "Digit. Blue g: memory map, program lines and data registers.",
}

HELP = """\
This is an RPN financial calculator with the HP 12c keyboard and functions.
Money you receive is positive. Money you pay is negative.

Everyday arithmetic
  2 ENTER 3 +          → 5
  200 ENTER 15 %       → 30, and Y is still 200, so + makes 230
  4 ENTER 5 ×          → 20, then g LSTx brings 5 back

A 30-year loan of 125,000 at 6.9%
  f FIN                clear the financial registers (f then x↔y)
  6.9 g 12÷            monthly rate into i
  360 n
  125000 PV
  0 FV
  PMT                  payment, shown as a negative number

Press n, i, PV, PMT, or FV after keying a number to store it.
Press the same key without keying a number to solve for it.
g BEG (the 7 key) means payments at the start of each period.
g END (the 8 key) is the usual end-of-period loan.

Cash flows
  f REG                clear storage
  79000 CHS g CFo      initial outlay
  14000 g CFj          later flows; g Nj repeats the last one
  13.5 i
  f NPV
  f IRR

Bonds (semiannual, actual/actual, par 100)
  yield i, coupon PMT, settlement ENTER maturity, f PRICE
  x↔y shows accrued interest; + adds it to the price
  price PV, coupon PMT, settlement ENTER maturity, f YTM

Depreciation
  cost PV, salvage FV, life n, year, then f SL, f SOYD, or f DB
  For declining balance, store the percent factor in i (200 for double)
  x↔y shows the remaining depreciable value

Dates
  A date is a number: month . day year, or day . month year.
  28 April 2004 is 4.282004 in M.DY, and 28.042004 in D.MY.
  g 4 (D.MY) switches to day.month.year and lights the D.MY flag.
  g 5 (M.DY) switches back to month.day.year.
  The year stays on the display once the date is complete.
  earlier ENTER later g ΔDYS     actual days; x↔y is the 30/360 count
  date ENTER days g DATE         new date, with weekday 1–7 at the right
  Monday is 1 and Sunday is 7

Display
  f 2                  two decimal places (f then a digit)
  f ·                  scientific notation
  f PREFIX             hold shows the full 10-digit mantissa (the ENTER key)

Programming
  f P/R                enter program mode (f then R/S)
  f PRGM               clear the program (f then R↓)
  key the steps, f P/R again, then R/S
  Up to 99 lines. Extra lines borrow registers from R.9 downward.
  g GTO and two digits jumps. In program mode, g GTO · and two digits moves the editor.

Keyboard
  Digits and + − × ÷ Enter
  n i p v              periods, rate, PV, FV
  m                    PMT
  f g s r              prefixes, STO, RCL
  c e x q              CHS, EEX, swap X and Y, roll the stack down
  Space                R/S
  Backspace            CLx
  Ctrl+C               copy the display
  F1                   this guide
"""


def memory_path() -> Path:
    folder = Path.home() / ".local" / "share" / "hp12c"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "memory.json"


class CalculatorWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="12c Financial Calculator")
        self.add_css_class("twelve-window")
        self.set_default_size(1020, 600)
        self.eng = HP12C()
        self._load()
        self._ann_labels = {}
        self._build()
        self.refresh()
        key = Gtk.EventControllerKey()
        key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)
        self.connect("close-request", self._on_close)

    def _build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("outer")
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        self.set_child(outer)

        case = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        case.add_css_class("case")
        outer.append(case)

        brand_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        brand = Gtk.Label(label="12c", xalign=0)
        brand.add_css_class("brand")
        sub = Gtk.Label(label="FINANCIAL CALCULATOR", xalign=0)
        sub.add_css_class("brand-sub")
        names.append(brand)
        names.append(sub)
        brand_row.append(names)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        brand_row.append(spacer)
        help_btn = Gtk.Button(label="Help")
        help_btn.add_css_class("help-link")
        help_btn.connect("clicked", lambda *_: self.show_help())
        brand_row.append(help_btn)
        case.append(brand_row)

        bezel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bezel.add_css_class("bezel")
        lcd = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lcd.add_css_class("lcd")
        digit_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.digits = Gtk.Label(label="0.00", xalign=1)
        self.digits.add_css_class("digits")
        self.digits.set_hexpand(True)
        self.dow = Gtk.Label(label="", xalign=1)
        self.dow.add_css_class("dow")
        digit_row.append(self.digits)
        digit_row.append(self.dow)
        lcd.append(digit_row)
        ann = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        for name in ("f", "g", "BEGIN", "D.MY", "C", "PRGM"):
            lab = Gtk.Label(label=name)
            lab.add_css_class("ann")
            ann.append(lab)
            self._ann_labels[name] = lab
        self.hint = Gtk.Label(label="", xalign=1)
        self.hint.add_css_class("hint")
        self.hint.set_hexpand(True)
        ann.append(self.hint)
        lcd.append(ann)
        bezel.append(lcd)
        case.append(bezel)

        self.plate = Gtk.Label(label="", xalign=0)
        self.plate.set_wrap(True)
        self.plate.add_css_class("plate-text")
        plate_box = Gtk.Box()
        plate_box.add_css_class("plate")
        plate_box.append(self.plate)
        case.append(plate_box)

        grid = Gtk.Grid(column_spacing=6, row_spacing=3)
        grid.set_column_homogeneous(True)
        grid.set_hexpand(True)
        grid.set_vexpand(True)
        # Gold legends sit on their own rows so BOND, DEPRECIATION, and CLEAR
        # can span the keys they belong to. ENTER then spans the last two key rows.
        legend_at = (0, 2, 4)
        key_at = (1, 3, 5, 6)
        brackets = {
            1: [(0, 1, "BOND"), (2, 4, "DEPRECIATION")],
            2: [(0, 5, "CLEAR")],
        }
        for index, row in enumerate(ROWS[:3]):
            labels = []
            for spec in row:
                labels.append("" if spec is None else spec[2])
            if index == 2:
                labels[5] = "PREFIX"
            self._attach_legend(grid, legend_at[index], labels, brackets.get(index, []))
        for index, row in enumerate(ROWS):
            for col_index, spec in enumerate(row):
                if spec is None:
                    continue
                grid.attach(self._cell(*spec), col_index, key_at[index], 1, 1)
        grid.attach(self._cell("enter", "ENTER", "", "LSTx", "enter-key"), 5, key_at[2], 1, 2)
        case.append(grid)

        foot = Gtk.Label(
            label="RPN   ·   f gold, then the key    ·   g blue, then the key    ·   F1 help",
            xalign=1,
        )
        foot.add_css_class("brand-sub")
        case.append(foot)

    def _attach_legend(self, grid, row, labels, brackets):
        covered = set()
        for start, end, title in brackets:
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            group.add_css_class("bracket")
            title_lab = Gtk.Label(label=title)
            title_lab.add_css_class("bracket-title")
            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
            for col in range(start, end + 1):
                lab = Gtk.Label(label=labels[col] or " ")
                lab.add_css_class("gold-lab")
                inner.append(lab)
                covered.add(col)
            group.append(title_lab)
            group.append(inner)
            grid.attach(group, start, row, end - start + 1, 1)
        for col, text in enumerate(labels):
            if col in covered:
                continue
            lab = Gtk.Label(label=text or " ")
            lab.add_css_class("gold-lab")
            lab.set_valign(Gtk.Align.END)
            grid.attach(lab, col, row, 1, 1)

    def _cell(self, key_id, primary, gold, blue, extra):
        del gold  # printed on the legend row, including the CLEAR / BOND brackets
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        button = Gtk.Button()
        button.add_css_class("calc-key")
        if extra:
            button.add_css_class(extra)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        prim = Gtk.Label(label=primary)
        prim.add_css_class("prim-lab")
        blue_lab = Gtk.Label(label=blue if blue else " ")
        blue_lab.add_css_class("blue-lab")
        inner.append(prim)
        inner.append(blue_lab)
        button.set_child(inner)
        button.set_hexpand(True)
        button.set_vexpand(True)
        box.set_hexpand(True)
        box.set_vexpand(True)
        tip = TIPS.get(key_id)
        if tip:
            button.set_tooltip_text(tip)
        button.connect("clicked", lambda *_b, k=key_id: self._press(k))
        box.append(button)
        return box

    def _press(self, key: str):
        self.eng.press(key)
        self.refresh()
        if self.eng.running:
            GLib.idle_add(self._burst)
        if self.eng.mantissa_hold:
            GLib.timeout_add(1200, self._drop_mantissa)
        self._save_soon()

    def _burst(self):
        if not self.eng.running:
            self.refresh()
            return False
        for _ in range(40):
            status = self.eng.step()
            if status == "pause":
                self.refresh()
                GLib.timeout_add(900, self._resume)
                return False
            if status in ("stop", "error") or not self.eng.running:
                self.refresh()
                self._save_soon()
                return False
        self.refresh()
        return True

    def _resume(self):
        if self.eng.running:
            GLib.idle_add(self._burst)
        return False

    def _drop_mantissa(self):
        if self.eng.mantissa_hold:
            self.eng.release_mantissa()
            self.refresh()
        return False

    def refresh(self):
        view = self.eng.lcd()
        self.digits.set_text(view["text"])
        self.digits.set_xalign(0 if view["align"] == "left" else 1)
        self.dow.set_text(view["dow"])
        flags = self.eng.annunciators()
        for name, lab in self._ann_labels.items():
            lit = bool(flags.get(name))
            lab.set_opacity(1.0 if lit else 0.28)
        hint = flags.get("hint") or ""
        if not hint:
            hint = "D.MY" if self.eng.dmy else "M.DY"
        if flags.get("run"):
            hint = (hint + "  running").strip()
        self.hint.set_text(hint)
        if view["off"]:
            self.plate.set_text("off  —  continuous memory is kept")
            return
        e = self.eng
        self.plate.set_text(
            "   ".join(
                [
                    "D.MY" if e.dmy else "M.DY",
                    "BEGIN" if e.begin else "END",
                    f"n {e.display(e.n)}",
                    f"i {e.display(e.i)}",
                    f"PV {e.display(e.pv)}",
                    f"PMT {e.display(e.pmt)}",
                    f"FV {e.display(e.fv)}",
                    f"Y {e.display(e.y)}",
                    f"Z {e.display(e.z)}",
                    f"T {e.display(e.t)}",
                ]
            )
        )

    def show_help(self):
        win = Gtk.Window(title="How to use the 12c")
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_default_size(640, 560)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        text = Gtk.Label(label=HELP, xalign=0, yalign=0)
        text.set_wrap(True)
        text.set_selectable(True)
        text.set_margin_start(16)
        text.set_margin_end(16)
        text.set_margin_top(12)
        text.set_margin_bottom(12)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(text)
        radix = Gtk.Button(label="Swap thousands separator  (1,000.00  /  1.000,00)")
        radix.set_margin_start(16)
        radix.set_margin_end(16)
        radix.set_margin_bottom(12)
        radix.connect("clicked", self._swap_radix)
        box.append(radix)
        scroll.set_child(box)
        win.set_child(scroll)
        win.present()

    def _swap_radix(self, _button):
        self.eng.euro = not self.eng.euro
        self.refresh()
        self._save_soon()

    def _on_key(self, _controller, keyval, _keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        if name in ("c", "C") and state & Gdk.ModifierType.CONTROL_MASK:
            self._copy()
            return True
        if name == "F1":
            self.show_help()
            return True
        if name in ("q", "Q") and state & Gdk.ModifierType.CONTROL_MASK:
            return False
        mapped = _shortcut(name)
        if mapped is None:
            return False
        self._press(mapped)
        return True

    def _copy(self):
        text = self.eng.lcd()["text"]
        self.get_clipboard().set(text)

    def _save_soon(self):
        if getattr(self, "_save_id", None):
            GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(400, self._save)

    def _save(self):
        self._save_id = None
        try:
            memory_path().write_text(json.dumps(self.eng.to_dict()))
        except OSError:
            pass
        return False

    def _load(self):
        path = memory_path()
        if not path.exists():
            return
        try:
            self.eng.load_dict(json.loads(path.read_text()))
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _on_close(self, *_args):
        self._save()
        return False


def _shortcut(name: str):
    digits = {str(n): str(n) for n in range(10)}
    digits.update({f"KP_{n}": str(n) for n in range(10)})
    table = {
        "Return": "enter", "KP_Enter": "enter",
        "BackSpace": "clx", "Escape": "clx", "Delete": "clx",
        "plus": "add", "KP_Add": "add",
        "minus": "sub", "KP_Subtract": "sub",
        "asterisk": "mul", "KP_Multiply": "mul",
        "slash": "div", "KP_Divide": "div",
        "period": "dot", "KP_Decimal": "dot", "comma": "dot",
        "percent": "pct",
        "n": "n", "N": "n", "i": "i", "I": "i",
        "p": "pv", "P": "pv", "m": "pmt", "M": "pmt",
        "v": "fv", "V": "fv",
        "f": "f", "F": "f", "g": "g", "G": "g",
        "s": "sto", "S": "sto", "r": "rcl", "R": "rcl",
        "c": "chs", "C": "chs", "e": "eex", "E": "eex",
        "x": "swap", "X": "swap",
        "space": "rs", "o": "on", "O": "on",
        "d": "roll", "D": "roll", "q": "roll", "Q": "roll",
    }
    if name in digits:
        return digits[name]
    return table.get(name)


class CalculatorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def do_activate(self):
        win = self.props.active_window
        if win is None:
            win = CalculatorWindow(self)
        win.present()


def main():
    app = CalculatorApp()
    raise SystemExit(app.run(None))
