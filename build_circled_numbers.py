#!/usr/bin/env python3
"""
Build "Circled Numbers" - an outlined-circle numeral font covering 1..100.

Each glyph is a ring (two concentric circles, opposite winding) with the
number optically centred inside it. Numerals are taken from Inter (SIL OFL),
so the generated font is an OFL derivative and ships under the OFL.

Usage:
    python build_circled_numbers.py --out dist
"""

import argparse
import math
import os
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

# --------------------------------------------------------------------------
# Design parameters (all in target units, UPM = 1000)
# --------------------------------------------------------------------------

UPM = 1000
ADVANCE = 880          # every glyph is the same width -> tabular in labels
CX = ADVANCE / 2       # circle centre x
CY = 350               # circle centre y (roughly cap-height/2)
R_OUTER = 390          # outer radius of the ring
RING = 54              # ring stroke thickness
INNER_PAD = 22         # clearance between ring inner edge and the numerals

ASCENDER = 800
DESCENDER = -200
CAP_HEIGHT = 700
X_HEIGHT = 500

# Per-digit-count typographic treatment. Condensing and tightening two- and
# three-digit numbers buys vertical size, which is what keeps them legible.
# max_cap is a ceiling on numeral cap-height as a fraction of the em; without
# it the pure geometric fit lets single digits swell to ~76% of the inner
# circle, which reads as cramped. ~60% of the inner diameter is the sweet spot.
FIT = {
    1: dict(xscale=1.00, tracking=0.000, max_cap=0.42),
    2: dict(xscale=0.95, tracking=-0.040, max_cap=0.37),
    3: dict(xscale=0.90, tracking=-0.060, max_cap=0.31),
}

CIRCLE_K = 0.5522847498307936  # cubic Bezier circle constant
CU2QU_ERROR = 0.6              # in target units; visually exact

# Standard Unicode homes for circled numbers (there are none past 50).
UNICODE_BLOCKS = [
    (1, 20, 0x2460),   # CIRCLED DIGIT ONE .. CIRCLED NUMBER TWENTY
    (21, 35, 0x3251),  # CIRCLED NUMBER TWENTY ONE .. THIRTY FIVE
    (36, 50, 0x32B1),  # CIRCLED NUMBER THIRTY SIX .. FIFTY
]
PUA_BASE = 0xE000      # uniform fallback: N -> U+E000 + N, for every N


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def draw_circle(pen, cx, cy, r, clockwise=True):
    """Emit one circular contour as four cubic arcs."""
    k = CIRCLE_K * r
    top, right, bottom, left = (cx, cy + r), (cx + r, cy), (cx, cy - r), (cx - r, cy)
    if clockwise:
        arcs = [
            ((cx + k, cy + r), (cx + r, cy + k), right),
            ((cx + r, cy - k), (cx + k, cy - r), bottom),
            ((cx - k, cy - r), (cx - r, cy - k), left),
            ((cx - r, cy + k), (cx - k, cy + r), top),
        ]
    else:
        arcs = [
            ((cx - k, cy + r), (cx - r, cy + k), left),
            ((cx - r, cy - k), (cx - k, cy - r), bottom),
            ((cx + k, cy - r), (cx + r, cy - k), right),
            ((cx + r, cy + k), (cx + k, cy + r), top),
        ]
    pen.moveTo(top)
    for c1, c2, end in arcs:
        pen.curveTo(c1, c2, end)
    pen.closePath()


class SamplingPen(BasePen):
    """Collects a dense point cloud of an outline.

    BasePen turns qCurveTo (including TrueType implied on-curve points) into
    plain cubics for us, so we only have to sample one curve type.
    """

    STEPS = 12

    def __init__(self, glyphSet=None):
        super().__init__(glyphSet)
        self.points = []

    def _moveTo(self, pt):
        self.points.append(pt)

    def _lineTo(self, pt):
        self.points.append(pt)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.points[-1] if self.points else (0, 0)
        for i in range(1, self.STEPS + 1):
            t = i / self.STEPS
            u = 1 - t
            x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
                 + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
            y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
                 + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
            self.points.append((x, y))

    def _closePath(self):
        pass


# --------------------------------------------------------------------------
# Source font (numerals)
# --------------------------------------------------------------------------

class DigitSource:
    def __init__(self, path):
        self.font = TTFont(path)
        self.upm = self.font["head"].unitsPerEm
        self.glyphSet = self.font.getGlyphSet()
        self.hmtx = self.font["hmtx"]
        cmap = self.font.getBestCmap()
        self.digit_glyph = {}
        for d in "0123456789":
            if ord(d) not in cmap:
                raise SystemExit(f"source font {path} is missing digit {d!r}")
            self.digit_glyph[d] = cmap[ord(d)]
        os2 = self.font["OS/2"]
        self.cap = getattr(os2, "sCapHeight", None) or int(self.upm * 0.72)

    def record(self, text, xscale, tracking_em):
        """Lay out `text` in source units, returning a RecordingPen."""
        rec = RecordingPen()
        pen_x = 0.0
        tracking = tracking_em * self.upm
        for ch in text:
            gn = self.digit_glyph[ch]
            t = Transform().translate(pen_x, 0).scale(xscale, 1.0)
            self.glyphSet[gn].draw(TransformPen(rec, t))
            pen_x += self.hmtx[gn][0] * xscale + tracking
        return rec


def measure(rec, cap):
    """Return (ink bounds, optical centre, max radius from that centre)."""
    bp = BoundsPen(None)
    rec.replay(bp)
    if bp.bounds is None:
        raise ValueError("empty outline")
    xMin, yMin, xMax, yMax = bp.bounds
    # Horizontal: centre on the ink. Vertical: centre on the cap-height box so
    # every number shares one baseline and round overshoots stay symmetric.
    cx = (xMin + xMax) / 2.0
    cy = cap / 2.0
    sp = SamplingPen(None)
    rec.replay(sp)
    rmax = max(math.hypot(x - cx, y - cy) for x, y in sp.points)
    return (xMin, yMin, xMax, yMax), (cx, cy), rmax


# --------------------------------------------------------------------------
# Font construction
# --------------------------------------------------------------------------

def single_byte_map(n):
    """Single-character access code for number `n` (CP1252-safe).

    1-9  -> '1'..'9'      10   -> '0'
    11-36 -> 'A'..'Z'     37-62 -> 'a'..'z'
    63-100 -> U+00C0..U+00E5
    """
    if 1 <= n <= 9:
        return ord("0") + n
    if n == 10:
        return ord("0")
    if 11 <= n <= 36:
        return ord("A") + (n - 11)
    if 37 <= n <= 62:
        return ord("a") + (n - 37)
    if 63 <= n <= 100:
        return 0x00C0 + (n - 63)
    raise ValueError(n)


def unicode_points(n):
    """All codepoints that should render number `n`."""
    pts = [PUA_BASE + n, single_byte_map(n)]
    for lo, hi, base in UNICODE_BLOCKS:
        if lo <= n <= hi:
            pts.append(base + (n - lo))
    return pts


def build_fit_scales(src, numbers):
    """One scale per digit-count, driven by the worst case in that group."""
    fit_radius = R_OUTER - RING - INNER_PAD
    scales = {}
    for n in numbers:
        text = str(n)
        cfg = FIT[len(text)]
        rec = src.record(text, cfg["xscale"], cfg["tracking"])
        _, _, rmax = measure(rec, src.cap)
        s = fit_radius / rmax
        # Never let a number grow past its cap-height ceiling.
        s = min(s, cfg["max_cap"] * UPM / src.cap)
        scales[len(text)] = min(scales.get(len(text), s), s)
    return scales


def make_glyph(src, n, scale):
    text = str(n)
    cfg = FIT[len(text)]
    rec = src.record(text, cfg["xscale"], cfg["tracking"])
    _, (scx, scy), _ = measure(rec, src.cap)

    tt = TTGlyphPen(None)

    # Ring: outer contour clockwise, inner counter-clockwise (non-zero fill).
    q = Cu2QuPen(tt, CU2QU_ERROR)
    draw_circle(q, CX, CY, R_OUTER, clockwise=True)
    draw_circle(q, CX, CY, R_OUTER - RING, clockwise=False)

    # Numerals: uniform scale about their optical centre, moved to circle centre.
    place = Transform().translate(CX, CY).scale(scale).translate(-scx, -scy)
    rec.replay(TransformPen(tt, place))

    return tt.glyph()


def make_notdef():
    """Hollow rectangle, drawn outer-clockwise / inner-counter-clockwise."""
    x0, x1, y0, y1, t = 80, ADVANCE - 80, 0, CAP_HEIGHT, 50
    pen = TTGlyphPen(None)
    for (a, b, c, d), clockwise in (((x0, y0, x1, y1), True),
                                    ((x0 + t, y0 + t, x1 - t, y1 - t), False)):
        corners = [(a, b), (a, d), (c, d), (c, b)]
        if not clockwise:
            corners.reverse()
        pen.moveTo(corners[0])
        for pt in corners[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def liga_feature(numbers):
    """Typing '42' becomes the circled 42 in shaping-aware apps."""
    def seq(n):
        parts = []
        for ch in str(n):
            parts.append("circled10" if ch == "0" else f"circled{ch}")
        return " ".join(parts)

    rules = []
    for n in sorted((n for n in numbers if n >= 10), key=lambda v: (-len(str(v)), v)):
        rules.append(f"    sub {seq(n)} by circled{n};")
    body = "\n".join(rules)
    return (
        "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n\n"
        f"lookup CircledNumberLigatures {{\n{body}\n}} CircledNumberLigatures;\n\n"
        "feature liga {\n    lookup CircledNumberLigatures;\n} liga;\n\n"
        "feature calt {\n    lookup CircledNumberLigatures;\n} calt;\n"
    )


def add_mac_cmap(font):
    """Add a (1,0) format-0 subtable so raw single-byte pipelines resolve."""
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    cmap = font["cmap"]
    best = font.getBestCmap()
    sub = CmapSubtable.newSubtable(0)
    sub.platformID, sub.platEncID, sub.language = 1, 0, 0
    sub.cmap = {cp: gn for cp, gn in best.items() if cp < 256}
    cmap.tables.append(sub)


def add_gasp(font):
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000F}  # grid-fit + grayscale at all sizes
    font["gasp"] = gasp


def build(src_path, out_path, numbers):
    src = DigitSource(src_path)
    scales = build_fit_scales(src, numbers)
    print("  fitted cap heights:", {k: round(v * src.cap) for k, v in scales.items()})

    order = [".notdef", "space"] + [f"circled{n}" for n in numbers]
    glyphs = {".notdef": make_notdef()}
    pen = TTGlyphPen(None)
    glyphs["space"] = pen.glyph()
    for n in numbers:
        glyphs[f"circled{n}"] = make_glyph(src, n, scales[len(str(n))])

    cmap = {0x0020: "space", 0x00A0: "space"}
    for n in numbers:
        for cp in unicode_points(n):
            cmap[cp] = f"circled{n}"

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)

    glyf = fb.font["glyf"]
    metrics = {}
    for gn in order:
        g = glyf[gn]
        g.recalcBounds(glyf)
        adv = 400 if gn == "space" else ADVANCE
        metrics[gn] = (adv, g.xMin if g.numberOfContours else 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=ASCENDER, descent=DESCENDER, lineGap=0)

    version = "1.000"
    family, style = "Circled Numbers", "Regular"
    ps_name = "CircledNumbers-Regular"
    fb.setupNameTable({
        "copyright": ("Circled Numbers. Numerals derived from Inter, "
                      "Copyright 2020 The Inter Project Authors "
                      "(https://github.com/rsms/inter), licensed under the SIL "
                      "Open Font License 1.1. This font is distributed under "
                      "the SIL Open Font License 1.1."),
        "familyName": family,
        "styleName": style,
        "uniqueFontIdentifier": f"{family}:{style}:{version}",
        "fullName": f"{family} {style}",
        "psName": ps_name,
        "version": f"Version {version}",
        "licenseDescription": ("This Font Software is licensed under the SIL Open "
                               "Font License, Version 1.1."),
        "licenseInfoURL": "https://scripts.sil.org/OFL",
        "sampleText": "1 7 25 42 99 100",
    })
    fb.setupOS2(
        sTypoAscender=750, sTypoDescender=-250, sTypoLineGap=0,
        usWinAscent=ASCENDER, usWinDescent=-DESCENDER,
        sCapHeight=CAP_HEIGHT, sxHeight=X_HEIGHT,
        usWeightClass=400, usWidthClass=5,
        fsType=0,                       # installable embedding (PDF/printers)
        achVendID="CNUM",
        ulCodePageRange1=(1 << 0),      # Latin-1 / CP1252
        panose=dict(bFamilyType=2, bSerifStyle=11, bWeight=6, bProportion=9,
                    bContrast=2, bStrokeVariation=2, bArmStyle=2, bLetterForm=2,
                    bMidline=2, bXHeight=4),
    )
    # post 2.0: keeps human-readable glyph names, which font editors and some
    # printer utilities expect. Costs ~1.5 KB.
    fb.setupPost(keepGlyphNames=True)
    fb.font["head"].lowestRecPPEM = 8
    add_gasp(fb.font)
    fb.addOpenTypeFeatures(liga_feature(numbers))
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    add_mac_cmap(fb.font)
    fb.setupDummyDSIG()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fb.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="TTF/WOFF2 to take numerals from")
    ap.add_argument("--out", default="dist/CircledNumbers-Regular.ttf")
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()

    numbers = list(range(1, args.max + 1))
    path = build(args.source, args.out, numbers)
    print(f"  wrote {path} ({os.path.getsize(path):,} bytes, "
          f"{len(numbers)} circled numbers)")

    # WOFF2 sibling for web use; the TTF is the one to install / send to printers.
    web = os.path.splitext(path)[0] + ".woff2"
    f = TTFont(path)
    f.flavor = "woff2"
    f.save(web)
    print(f"  wrote {web} ({os.path.getsize(web):,} bytes)")


if __name__ == "__main__":
    main()
