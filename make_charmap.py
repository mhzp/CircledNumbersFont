#!/usr/bin/env python3
"""Emit charmap.csv: every way to reach each circled number."""
import csv
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from build_circled_numbers import UNICODE_BLOCKS, PUA_BASE, single_byte_map


def standard_cp(n):
    for lo, hi, base in UNICODE_BLOCKS:
        if lo <= n <= hi:
            return base + (n - lo)
    return None


def main(out="charmap.csv"):
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["number", "type_this", "byte_hex", "pua_codepoint",
                    "standard_unicode", "notes"])
        for n in range(1, 101):
            b = single_byte_map(n)
            std = standard_cp(n)
            w.writerow([
                n,
                chr(b),
                f"0x{b:02X}",
                f"U+{PUA_BASE + n:04X}",
                f"U+{std:04X}" if std else "",
                "" if std else "no standard Unicode codepoint exists above 50",
            ])
    print(f"wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
