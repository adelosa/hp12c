"""Handbook examples for the 12c engine."""

import unittest

from hp12c.engine import HP12C


def tap(calc, *keys):
    for key in keys:
        calc.press(key)


def num(calc, text):
    for ch in str(text):
        if ch == ".":
            calc.press("dot")
        elif ch == "-":
            calc.press("chs")
        else:
            calc.press(ch)


class EngineTests(unittest.TestCase):
    def fresh(self):
        calc = HP12C()
        tap(calc, "f", "swap")  # CLEAR FIN
        return calc

    def assertClose(self, value, expected, places=2):
        self.assertAlmostEqual(value, expected, places=places)

    def test_stack_and_constant(self):
        c = HP12C()
        num(c, "4.38")
        tap(c, "enter", "enter", "enter")
        num(c, "15")
        tap(c, "mul")
        self.assertClose(c.x, 65.70)
        tap(c, "clx")
        num(c, "75")
        tap(c, "mul")
        self.assertClose(c.x, 328.50)
        tap(c, "clx")
        num(c, "250")
        tap(c, "mul")
        self.assertClose(c.x, 1095.00)

    def test_percent_keeps_base(self):
        c = HP12C()
        num(c, "200")
        tap(c, "enter")
        num(c, "15")
        tap(c, "pct")
        self.assertClose(c.x, 30)
        self.assertClose(c.y, 200)
        tap(c, "add")
        self.assertClose(c.x, 230)
        num(c, "150")
        tap(c, "enter")
        num(c, "200")
        tap(c, "dpct")
        self.assertClose(c.x, 33.33)

    def test_powers_and_last_x(self):
        c = HP12C()
        num(c, "2")
        tap(c, "enter")
        num(c, "10")
        tap(c, "yx")
        self.assertClose(c.x, 1024)
        num(c, "9")
        tap(c, "g", "yx")
        self.assertClose(c.x, 3)
        num(c, "5")
        tap(c, "g", "3")
        self.assertClose(c.x, 120)
        num(c, "3")
        tap(c, "enter")
        num(c, "4")
        tap(c, "mul", "g", "enter")
        self.assertClose(c.x, 4)

    def test_loan_payment(self):
        c = self.fresh()
        num(c, "6.9")
        tap(c, "g", "i")
        num(c, "360")
        tap(c, "n")
        num(c, "125000")
        tap(c, "pv")
        num(c, "0")
        tap(c, "fv")
        tap(c, "pmt")
        self.assertClose(c.x, -823.25)

    def test_cabin_payments_and_balloon(self):
        c = self.fresh()
        num(c, "10.5")
        tap(c, "g", "i")
        num(c, "35000")
        tap(c, "pv")
        num(c, "325")
        tap(c, "chs", "pmt")
        tap(c, "g", "8")  # END
        tap(c, "n")
        self.assertClose(c.x, 328)
        self.assertClose(c.n, 328)
        num(c, "12")
        tap(c, "div")
        self.assertClose(c.x, 27.33)
        num(c, "328")
        tap(c, "n", "fv")
        self.assertClose(c.x, 181.89)
        tap(c, "rcl", "pmt", "add")
        self.assertClose(c.x, -143.11)

    def test_payment_mode_keys_and_begin_indicator(self):
        c = HP12C()
        self.assertFalse(c.begin)
        self.assertFalse(c.annunciators()["BEGIN"])
        tap(c, "g", "7")
        self.assertTrue(c.begin)
        self.assertTrue(c.annunciators()["BEGIN"])
        self.assertFalse(c.annunciators()["g"])
        tap(c, "g", "8")
        self.assertFalse(c.begin)
        self.assertFalse(c.annunciators()["BEGIN"])

    def test_begin_future_value(self):
        c = self.fresh()
        num(c, "2")
        tap(c, "g", "n")
        self.assertClose(c.n, 24)
        num(c, "6.25")
        tap(c, "g", "i")
        num(c, "50")
        tap(c, "chs", "pmt")
        tap(c, "g", "7")  # BEG
        tap(c, "fv")
        self.assertClose(c.x, 1281.34)
        self.assertTrue(c.annunciators()["BEGIN"])

    def test_depreciating_property(self):
        c = self.fresh()
        num(c, "6")
        tap(c, "n")
        num(c, "2")
        tap(c, "chs", "i")
        num(c, "32000")
        tap(c, "chs", "pv", "fv")
        self.assertClose(c.x, 28346.96)

    def test_odd_period_payment(self):
        c = self.fresh()
        tap(c, "g", "8")
        tap(c, "sto", "eex")  # compound odd period
        self.assertTrue(c.annunciators()["C"])
        num(c, "2.152004")
        tap(c, "enter")
        num(c, "3.012004")
        tap(c, "g", "eex")  # ΔDYS
        self.assertClose(c.x, 15)
        tap(c, "swap")
        self.assertClose(c.x, 16)  # 30/360
        num(c, "30")
        tap(c, "div")
        num(c, "36")
        tap(c, "add", "n")
        self.assertClose(c.n, 36.53, places=2)
        num(c, "15")
        tap(c, "g", "i")
        num(c, "4500")
        tap(c, "pv", "pmt")
        self.assertClose(c.x, -157.03)

    def test_odd_period_apr(self):
        c = self.fresh()
        # C annunciator starts off: simple interest for the odd period.
        num(c, "7.192004")
        tap(c, "enter")
        num(c, "8.012004")
        tap(c, "g", "eex")
        self.assertClose(c.x, 13)
        num(c, "30")
        tap(c, "div")
        num(c, "42")
        tap(c, "add", "n")
        num(c, "3950")
        tap(c, "pv")
        num(c, "120")
        tap(c, "chs", "pmt", "i")
        self.assertClose(c.x, 1.16)
        num(c, "12")
        tap(c, "mul")
        self.assertClose(c.x, 13.95)

    def test_amortization(self):
        c = self.fresh()
        num(c, "13.25")
        tap(c, "g", "i")
        num(c, "50000")
        tap(c, "pv")
        num(c, "573.35")
        tap(c, "chs", "pmt")
        tap(c, "g", "8")
        num(c, "12")
        tap(c, "f", "n")
        self.assertClose(c.x, -6608.89)
        tap(c, "swap")
        self.assertClose(c.x, -271.31)
        tap(c, "rcl", "pv")
        self.assertClose(c.x, 49728.69)
        tap(c, "rcl", "n")
        self.assertClose(c.x, 12)

    def test_npv_and_irr(self):
        c = HP12C()
        tap(c, "f", "clx")  # CLEAR REG
        num(c, "79000")
        tap(c, "chs", "g", "pv")
        num(c, "14000")
        tap(c, "g", "pmt")
        num(c, "11000")
        tap(c, "g", "pmt")
        num(c, "10000")
        tap(c, "g", "pmt")
        num(c, "3")
        tap(c, "g", "fv")
        num(c, "9100")
        tap(c, "g", "pmt")
        num(c, "9000")
        tap(c, "g", "pmt")
        num(c, "2")
        tap(c, "g", "fv")
        num(c, "4500")
        tap(c, "g", "pmt")
        num(c, "100000")
        tap(c, "g", "pmt")
        tap(c, "rcl", "n")
        self.assertClose(c.x, 7)
        num(c, "13.5")
        tap(c, "i", "f", "pv")
        self.assertClose(c.x, 907.77)
        tap(c, "f", "fv")
        self.assertClose(c.x, 13.72)
        self.assertClose(c.i, 13.72)

    def test_cash_flow_review_decrements_n(self):
        c = HP12C()
        tap(c, "f", "clx")
        num(c, "10")
        tap(c, "g", "pv")
        num(c, "5")
        tap(c, "g", "pmt")
        num(c, "7")
        tap(c, "g", "pmt")
        tap(c, "rcl", "g", "pmt")
        self.assertClose(c.x, 7)
        self.assertClose(c.n, 1)
        tap(c, "rcl", "g", "pmt")
        self.assertClose(c.x, 5)
        self.assertClose(c.n, 0)

    def test_bond_price_and_yield(self):
        c = self.fresh()
        tap(c, "g", "5")  # M.DY
        num(c, "8.25")
        tap(c, "i")
        num(c, "6.75")
        tap(c, "pmt")
        num(c, "4.282004")
        tap(c, "enter")
        num(c, "6.042018")
        tap(c, "f", "yx")
        self.assertClose(c.x, 87.62)
        tap(c, "add")
        self.assertClose(c.x, 90.31)
        # Quoted price 88 3/8, same coupon and dates.
        c2 = self.fresh()
        tap(c2, "g", "5")
        num(c2, "3")
        tap(c2, "enter")
        num(c2, "8")
        tap(c2, "div")
        num(c2, "88")
        tap(c2, "add", "pv")
        num(c2, "6.75")
        tap(c2, "pmt")
        num(c2, "4.282004")
        tap(c2, "enter")
        num(c2, "6.042018")
        tap(c2, "f", "rec")
        self.assertClose(c2.x, 8.15)

    def test_declining_balance(self):
        c = self.fresh()
        num(c, "10000")
        tap(c, "pv")
        num(c, "500")
        tap(c, "fv")
        num(c, "5")
        tap(c, "n")
        num(c, "200")
        tap(c, "i")
        num(c, "1")
        tap(c, "f", "pct")
        self.assertClose(c.x, 4000)
        tap(c, "swap")
        self.assertClose(c.x, 5500)
        num(c, "2")
        tap(c, "f", "pct")
        self.assertClose(c.x, 2400)
        tap(c, "swap")
        self.assertClose(c.x, 3100)
        num(c, "3")
        tap(c, "f", "pct")
        self.assertClose(c.x, 1440)
        tap(c, "swap")
        self.assertClose(c.x, 1660)

    def test_straight_line(self):
        c = self.fresh()
        num(c, "10000")
        tap(c, "pv")
        num(c, "500")
        tap(c, "fv")
        num(c, "5")
        tap(c, "n")
        num(c, "1")
        tap(c, "f", "pctt")
        self.assertClose(c.x, 1900)
        tap(c, "swap")
        self.assertClose(c.x, 7600)

    def test_statistics(self):
        c = HP12C()
        tap(c, "f", "sst")
        pairs = [(32, 17000), (40, 25000), (45, 26000), (40, 20000),
                 (38, 21000), (50, 28000), (35, 15000)]
        for hours, sales in pairs:
            num(c, str(hours))
            tap(c, "enter")
            num(c, str(sales))
            tap(c, "sum")
        tap(c, "g", "0")
        self.assertClose(c.x, 21714.29)
        tap(c, "swap")
        self.assertClose(c.x, 40)
        tap(c, "g", "dot")
        self.assertClose(c.x, 4820.59)
        tap(c, "swap")
        self.assertClose(c.x, 6.03)
        num(c, "48")
        tap(c, "g", "1")
        self.assertClose(c.x, 28818.93)
        tap(c, "swap")
        self.assertClose(c.x, 0.90, places=2)

    def test_dates(self):
        c = HP12C()
        num(c, "1.012004")
        tap(c, "enter")
        num(c, "31")
        tap(c, "g", "chs")
        # 1 Jan 2004 is a Thursday (4); 1 Feb 2004 is a Sunday (7).
        self.assertEqual(c.date_dow, 7)
        self.assertAlmostEqual(c.x, 2.012004, places=6)
        self.assertEqual(c.lcd()["text"], "2.012004")
        self.assertEqual(c.lcd()["dow"], "7")
        num(c, "1.012004")
        tap(c, "enter")
        num(c, "2.012004")
        tap(c, "g", "eex")
        self.assertClose(c.x, 31)

    def test_date_entry_keeps_the_year_and_mode(self):
        c = HP12C()
        self.assertFalse(c.annunciators()["D.MY"])
        c.press("g")
        self.assertTrue(c.annunciators()["g"])
        self.assertEqual(c.annunciators()["hint"], "g")
        c.press("4")
        self.assertTrue(c.dmy)
        self.assertTrue(c.annunciators()["D.MY"])
        self.assertFalse(c.annunciators()["g"])
        # 28 April 2004 in day.month.year. FIX 2 must not swallow the year.
        num(c, "28.04")
        self.assertEqual(c.lcd()["text"], "28.04")
        num(c, "2004")
        self.assertEqual(c.lcd()["text"], "28.042004")
        tap(c, "enter")
        self.assertEqual(c.lcd()["text"], "28.042004")
        # g 5 returns to month.day.year. 28.042004 is not a valid month, so it
        # falls back to the FIX display; g 4 recognises it as a date again.
        tap(c, "g", "5")
        self.assertFalse(c.dmy)
        self.assertFalse(c.annunciators()["D.MY"])
        self.assertEqual(c.lcd()["text"], "28.04")
        tap(c, "g", "4")
        self.assertEqual(c.lcd()["text"], "28.042004")
        tap(c, "clx")
        num(c, "4.282004")
        tap(c, "g", "5")
        self.assertEqual(c.lcd()["text"], "4.282004")
        tap(c, "enter")
        self.assertEqual(c.lcd()["text"], "4.282004")

    def test_program_adds(self):
        c = HP12C()
        tap(c, "f", "rs")          # program mode
        tap(c, "f", "roll")        # CLEAR PRGM
        num(c, "2")
        tap(c, "enter")
        num(c, "3")
        tap(c, "add")
        tap(c, "f", "rs")          # run mode
        tap(c, "rs")
        c.run()
        self.assertClose(c.x, 5)

    def test_conditional_skip(self):
        c = HP12C()
        tap(c, "f", "rs", "f", "roll")
        num(c, "1")
        tap(c, "g", "clx")  # x=0?
        num(c, "0")
        tap(c, "f", "rs", "rs")
        c.run()
        self.assertClose(c.x, 1)

    def test_storage_and_memory_map(self):
        c = HP12C()
        num(c, "42")
        tap(c, "sto", "dot", "9", "clx", "rcl", "dot", "9")
        self.assertClose(c.x, 42)
        tap(c, "g", "9")
        self.assertEqual(c.lcd()["text"], "P-08  r-20")
        tap(c, "f", "rs", "f", "roll")
        for _ in range(9):
            num(c, "1")
        self.assertEqual(c.reg_count(), 19)
        tap(c, "f", "rs")
        num(c, "3")
        tap(c, "sto", "dot", "9")
        self.assertEqual(c.error, 6)

    def test_divide_by_zero(self):
        c = HP12C()
        num(c, "1")
        tap(c, "enter", "0", "div")
        self.assertEqual(c.error, 0)
        self.assertEqual(c.lcd()["text"], "Error 0")
        tap(c, "clx")  # clears the error and is consumed
        self.assertIsNone(c.error)
        tap(c, "clx")
        self.assertClose(c.x, 0)

    def test_display_grouping(self):
        c = HP12C()
        num(c, "21714.285")
        tap(c, "enter")
        self.assertEqual(c.format_number(c.x), "21,714.29")
        tap(c, "f", "dot")
        text = c.format_number(c.x)
        self.assertTrue(text.startswith("2.171428") or text.startswith("2.171429"))


if __name__ == "__main__":
    unittest.main()
