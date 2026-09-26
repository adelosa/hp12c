# 12c Financial Calculator

A native Linux desktop calculator styled on the classic HP 12c. It uses the same RPN keyboard and the same financial functions: time value of money, amortization, NPV and IRR, bonds, depreciation, dates, statistics, and keystroke programming.

## Run

```bash
./hp12c-run
```

Requires Python 3 and GTK 4 (`python3-gi`, `gir1.2-gtk-4.0`).

The window title is **12c Financial Calculator**. Press **Help** or **F1** for the keystroke guide. Registers, the stack, and any program you enter are kept in `~/.local/share/hp12c/memory.json`.

## Checks

```bash
python3 -m unittest tests.test_engine
```

The tests follow worked examples from the HP 12c owner's handbook, including the mortgage payment, odd-period interest, amortization, NPV/IRR, and the Treasury bond price.
