#!/usr/bin/env python3
"""Generate a self-contained HTML cheat sheet with the fonts inlined."""
import base64
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_circled_numbers import (ADVANCE, PUA_BASE, UNICODE_BLOCKS, UPM,
                                   single_byte_map)


def data_uri(path):
    b64 = base64.b64encode(open(path, "rb").read()).decode("ascii")
    return f"data:font/woff2;charset=utf-8;base64,{b64}"


def standard_cp(n):
    for lo, hi, base in UNICODE_BLOCKS:
        if lo <= n <= hi:
            return base + (n - lo)
    return None


def build(ttf, woff2, body_regular, body_semibold, out):
    ttf_kb = os.path.getsize(ttf) / 1024
    faces = (
        f'@font-face{{font-family:"CircledNumbers";src:url("{data_uri(woff2)}") '
        'format("woff2");font-weight:400;font-style:normal;}\n'
        f'@font-face{{font-family:"SheetSans";src:url("{data_uri(body_regular)}") '
        'format("woff2");font-weight:400;font-style:normal;font-display:block;}\n'
        f'@font-face{{font-family:"SheetSans";src:url("{data_uri(body_semibold)}") '
        'format("woff2");font-weight:600;font-style:normal;font-display:block;}'
    )

    # --- specimen grid: glyph + the single keystroke that produces it -------
    cells = []
    for n in range(1, 101):
        std = standard_cp(n)
        copy_cp = std if std else PUA_BASE + n
        note = f"U+{copy_cp:04X}" + ("" if std else " (private use)")
        key = html.escape(chr(single_byte_map(n)))
        cells.append(
            f'<button class="cell" data-copy="{copy_cp}" data-n="{n}" '
            f'data-note="{note}" aria-label="Number {n}, type {key}">'
            f'<span class="cell-glyph">{chr(PUA_BASE + n)}</span>'
            f'<span class="cell-key">{key}</span></button>'
        )
    grid = "\n".join(cells)

    # --- full character map ------------------------------------------------
    rows = []
    for n in range(1, 101):
        std = standard_cp(n)
        b = single_byte_map(n)
        rows.append(
            "<tr>"
            f'<td class="t-glyph">{chr(PUA_BASE + n)}</td>'
            f'<td class="t-num">{n}</td>'
            f'<td class="t-key">{html.escape(chr(b))}</td>'
            f'<td class="t-code">0x{b:02X}</td>'
            f'<td class="t-code">U+{PUA_BASE + n:04X}</td>'
            f'<td class="t-code t-std">{f"U+{std:04X}" if std else "&mdash;"}</td>'
            "</tr>"
        )
    half = 50
    table_a, table_b = "\n".join(rows[:half]), "\n".join(rows[half:])

    # --- 203 dpi size ladder ----------------------------------------------
    ladder = []
    for pt in (8, 10, 12, 14, 18):
        px = round(pt / 72 * 203)
        warn = "low" if pt < 12 else "ok"
        sample = "".join(chr(PUA_BASE + v) for v in (7, 12, 42, 88, 100))
        ladder.append(
            f'<div class="rung"><div class="rung-meta"><span class="rung-pt">{pt} pt</span>'
            f'<span class="rung-px">{px} dots</span>'
            f'<span class="chip chip-{warn}">{"marginal" if warn == "low" else "safe"}</span></div>'
            f'<div class="rung-sample" style="font-size:{px}px">{sample}</div></div>'
        )
    ladder = "\n".join(ladder)

    tpl = TEMPLATE
    for k, v in {
        "__FACES__": faces,
        "__GRID__": grid,
        "__TABLE_A__": table_a,
        "__TABLE_B__": table_b,
        "__LADDER__": ladder,
        "__TTFKB__": f"{ttf_kb:.0f} KB",
        "__UPM__": str(UPM),
        "__ADV__": str(ADVANCE),
    }.items():
        tpl = tpl.replace(k, v)

    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(tpl)
    print(f"wrote {out} ({os.path.getsize(out)/1024:.0f} KB)")


TEMPLATE = r"""<title>Circled Numbers 1&ndash;100</title>
<style>
__FACES__

:root{
  --ground:#F4F7F6; --surface:#FFFFFF; --surface-2:#EDF2F1;
  --ink:#121918; --muted:#64726F; --rule:#DBE3E1;
  --accent:#0F6E62; --accent-soft:#E1EFEC; --accent-ink:#0B534A;
  --warn:#A2560C; --warn-soft:#FBEEE0;
  --fs-xs:.6875rem; --fs-sm:.8125rem; --fs-base:.9375rem;
  --fs-lg:1.125rem; --fs-xl:1.5rem; --fs-2xl:2.25rem; --fs-3xl:3.25rem;
  --mono:ui-monospace,"Cascadia Mono","SF Mono",Consolas,"Liberation Mono",monospace;
  --sans:"SheetSans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --maxw:74rem;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0E1312; --surface:#161D1C; --surface-2:#1D2625;
    --ink:#E7EDEB; --muted:#8E9C99; --rule:#263130;
    --accent:#46C4B0; --accent-soft:#122B28; --accent-ink:#7FDCCB;
    --warn:#E0A458; --warn-soft:#2A2015;
  }
}
:root[data-theme="dark"]{
  --ground:#0E1312; --surface:#161D1C; --surface-2:#1D2625;
  --ink:#E7EDEB; --muted:#8E9C99; --rule:#263130;
  --accent:#46C4B0; --accent-soft:#122B28; --accent-ink:#7FDCCB;
  --warn:#E0A458; --warn-soft:#2A2015;
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); font-size:var(--fs-base); line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:var(--maxw); margin:0 auto; padding:2.5rem 1.5rem 4rem;
  display:flex; flex-direction:column; gap:3.25rem;}

/* ---------- masthead ---------- */
.masthead{display:grid; grid-template-columns:minmax(0,1fr) auto; gap:2rem;
  align-items:end; border-bottom:2px solid var(--ink); padding-bottom:1.5rem;}
.eyebrow{font-size:var(--fs-xs); letter-spacing:.13em; text-transform:uppercase;
  color:var(--accent-ink); font-weight:600; margin:0 0 .5rem;}
h1{font-size:var(--fs-3xl); line-height:1.02; margin:0; font-weight:600;
  letter-spacing:-.025em; text-wrap:balance;}
.lede{margin:.75rem 0 0; color:var(--muted); max-width:34em;}
.mast-glyphs{font-family:"CircledNumbers"; font-size:3.5rem; line-height:1;
  color:var(--accent); white-space:nowrap;}
.facts{display:flex; flex-wrap:wrap; gap:.4rem 1.25rem; margin-top:1.25rem;
  font-family:var(--mono); font-size:var(--fs-xs); color:var(--muted);}
.facts b{color:var(--ink); font-weight:600;}

/* ---------- sections ---------- */
section{display:flex; flex-direction:column; gap:1.25rem;}
h2{font-size:var(--fs-xl); margin:0; font-weight:600; letter-spacing:-.015em;}
.sub{margin:-.6rem 0 0; color:var(--muted); font-size:var(--fs-sm); max-width:60em;}

/* ---------- specimen grid ---------- */
.grid{display:grid; grid-template-columns:repeat(10,minmax(0,1fr)); gap:.375rem;}
@media (max-width:720px){.grid{grid-template-columns:repeat(5,minmax(0,1fr));}}
.cell{display:flex; flex-direction:column; align-items:center; gap:.15rem;
  padding:.6rem .25rem .45rem; background:var(--surface);
  border:1px solid var(--rule); border-radius:3px; cursor:pointer;
  color:var(--ink); font:inherit; transition:border-color .12s, background .12s;}
.cell:hover{border-color:var(--accent); background:var(--accent-soft);}
.cell:focus-visible{outline:2px solid var(--accent); outline-offset:2px;}
.cell-glyph{font-family:"CircledNumbers"; font-size:1.85rem; line-height:1.1;}
.cell-key{font-family:var(--mono); font-size:var(--fs-xs); color:var(--muted);}
.cell:hover .cell-key{color:var(--accent-ink);}

/* ---------- routes ---------- */
.routes{display:grid; grid-template-columns:repeat(auto-fit,minmax(15rem,1fr)); gap:1rem;}
.route{background:var(--surface); border:1px solid var(--rule); border-radius:4px;
  padding:1.1rem 1.15rem; display:flex; flex-direction:column; gap:.55rem;}
.route h3{margin:0; font-size:var(--fs-base); font-weight:600;}
.route p{margin:0; font-size:var(--fs-sm); color:var(--muted);}
.route .demo{font-family:var(--mono); font-size:var(--fs-sm);
  background:var(--surface-2); border-radius:3px; padding:.5rem .65rem;
  display:flex; align-items:center; gap:.6rem; flex-wrap:wrap;}
.demo .out{font-family:"CircledNumbers"; font-size:1.4rem; color:var(--accent);}
.route .where{font-size:var(--fs-xs); color:var(--muted); margin-top:auto;
  padding-top:.5rem; border-top:1px solid var(--rule);}

/* ---------- table ---------- */
.maps{display:grid; grid-template-columns:repeat(auto-fit,minmax(23rem,1fr)); gap:1.5rem;}
.tablebox{overflow-x:auto; border:1px solid var(--rule); border-radius:4px;
  background:var(--surface);}
table{border-collapse:collapse; width:100%; font-size:var(--fs-sm);}
th{position:sticky; top:0; background:var(--surface-2); text-align:left;
  font-size:var(--fs-xs); letter-spacing:.07em; text-transform:uppercase;
  color:var(--muted); font-weight:600; padding:.5rem .6rem; white-space:nowrap;
  border-bottom:1px solid var(--rule);}
td{padding:.28rem .6rem; border-bottom:1px solid var(--rule); white-space:nowrap;}
tr:last-child td{border-bottom:0;}
tbody tr:hover{background:var(--accent-soft);}
.t-glyph{font-family:"CircledNumbers"; font-size:1.25rem; width:1.5rem;}
.t-num,.t-code{font-family:var(--mono); font-variant-numeric:tabular-nums;}
.t-num{color:var(--muted);}
.t-key{font-family:var(--mono); font-weight:600;}
.t-code{font-size:var(--fs-xs); color:var(--muted);}
.t-std{color:var(--accent-ink);}

/* ---------- size ladder ---------- */
.ladder{display:flex; flex-direction:column; gap:.5rem;}
.rung{display:grid; grid-template-columns:11rem minmax(0,1fr); gap:1rem;
  align-items:center; background:var(--surface); border:1px solid var(--rule);
  border-radius:4px; padding:.7rem 1rem;}
.rung-meta{display:flex; align-items:center; gap:.5rem;}
.rung-pt{font-family:var(--mono); font-weight:600; font-variant-numeric:tabular-nums;}
.rung-px{font-family:var(--mono); font-size:var(--fs-xs); color:var(--muted);}
.rung-sample{font-family:"CircledNumbers"; line-height:1.25; word-spacing:.35em;
  overflow-x:auto;}
.chip{font-size:var(--fs-xs); padding:.1rem .45rem; border-radius:999px;
  font-weight:600; letter-spacing:.03em;}
.chip-ok{background:var(--accent-soft); color:var(--accent-ink);}
.chip-low{background:var(--warn-soft); color:var(--warn);}
@media (max-width:640px){.rung{grid-template-columns:1fr;}}

/* ---------- notes / footer ---------- */
.note{background:var(--surface); border-left:3px solid var(--warn);
  border-radius:0 4px 4px 0; padding:.9rem 1.1rem; font-size:var(--fs-sm);}
.note b{font-weight:600;}
footer{border-top:1px solid var(--rule); padding-top:1.25rem; color:var(--muted);
  font-size:var(--fs-sm); display:flex; flex-direction:column; gap:.4rem;}
code{font-family:var(--mono); font-size:.92em; background:var(--surface-2);
  padding:.1em .35em; border-radius:3px;}

/* ---------- copy toast ---------- */
#toast{position:fixed; left:50%; bottom:1.75rem; transform:translateX(-50%) translateY(.75rem);
  background:var(--ink); color:var(--ground); padding:.55rem 1rem; border-radius:4px;
  font-size:var(--fs-sm); opacity:0; pointer-events:none; transition:opacity .16s, transform .16s;}
#toast.show{opacity:1; transform:translateX(-50%) translateY(0);}
@media (prefers-reduced-motion:reduce){*{transition:none!important;}}

@media print{
  :root{--ground:#fff; --surface:#fff; --surface-2:#f2f2f2; --ink:#000;
        --muted:#555; --rule:#bbb; --accent:#000; --accent-soft:#fff; --accent-ink:#000;}
  .wrap{padding:0; gap:1.75rem;} .cell{cursor:default;}
  section,.rung,.route{break-inside:avoid;} #toast{display:none;}
}
</style>

<div class="wrap">

  <header class="masthead">
    <div>
      <p class="eyebrow">TrueType specimen &amp; character map</p>
      <h1>Circled Numbers</h1>
      <p class="lede">One glyph per number, 1 to 100, drawn as an outlined ring
        with the numeral optically centred inside it. Built for label printers:
        fixed advance width, embeddable, no shaping required.</p>
      <div class="facts">
        <span><b>102</b> glyphs</span>
        <span><b>__TTFKB__</b> TTF</span>
        <span><b>__UPM__</b> upm</span>
        <span><b>__ADV__</b> advance</span>
        <span><b>OFL 1.1</b></span>
      </div>
    </div>
    <div class="mast-glyphs" aria-hidden="true">&#xE001;&#xE007;&#xE02A;&#xE064;</div>
  </header>

  <section>
    <h2>All one hundred</h2>
    <p class="sub">Each tile shows the glyph above the single key that produces
      it. Click any tile to copy the character.</p>
    <div class="grid">
__GRID__
    </div>
  </section>

  <section>
    <h2>Four ways to get one</h2>
    <p class="sub">Whichever of these your software supports, one of them works.
      They all resolve to the same glyph.</p>
    <div class="routes">

      <div class="route">
        <h3>Type the number</h3>
        <div class="demo"><span>42</span><span>&rarr;</span><span class="out">&#xE02A;</span></div>
        <p>The <code>liga</code> and <code>calt</code> features fold a digit run
          into one circled glyph. Covers 1&ndash;100.</p>
        <p class="where">Word, InDesign, Illustrator, browsers, modern label designers</p>
      </div>

      <div class="route">
        <h3>One keystroke each</h3>
        <div class="demo"><span>Q</span><span>&rarr;</span><span class="out">&#xE01B;</span></div>
        <p><code>1</code>&ndash;<code>9</code> give 1&ndash;9, <code>0</code>
          gives 10, <code>A</code>&ndash;<code>Z</code> give 11&ndash;36,
          <code>a</code>&ndash;<code>z</code> give 37&ndash;62, and
          <code>&Agrave;</code>&ndash;<code>&aring;</code> give 63&ndash;100.</p>
        <p class="where">Anywhere &mdash; plain text fields, raw byte streams, ZPL</p>
      </div>

      <div class="route">
        <h3>Standard Unicode</h3>
        <div class="demo"><span>U+2469</span><span>&rarr;</span><span class="out">&#xE00A;</span></div>
        <p><code>U+2460</code>&ndash;<code>U+2473</code>,
          <code>U+3251</code>&ndash;<code>U+325F</code> and
          <code>U+32B1</code>&ndash;<code>U+32BF</code>. Unicode stops at 50 &mdash;
          there are no encoded circled numbers above it.</p>
        <p class="where">1&ndash;50 only; also renders in other fonts</p>
      </div>

      <div class="route">
        <h3>Private use area</h3>
        <div class="demo"><span>U+E000&nbsp;+&nbsp;N</span><span>&rarr;</span><span class="out">&#xE064;</span></div>
        <p>One rule with no special cases: 7 is <code>U+E007</code>, 42 is
          <code>U+E02A</code>, 100 is <code>U+E064</code>.</p>
        <p class="where">Best for generated output and mail merges</p>
      </div>

    </div>
    <div class="note"><b>The trade-off:</b> because <code>1</code> gives
      &#xE001; and <code>2</code> gives &#xE002;, any app with ligatures on
      turns <code>12</code> into &#xE00C;. That is the intent &mdash; but it means
      you cannot sit &#xE001; and &#xE002; directly next to each other by typing.
      Separate them with a space, or address them by codepoint instead.</div>
  </section>

  <section>
    <h2>Printing small</h2>
    <p class="sub">Rendered at the pixel size matching each point size on a
      203 dpi thermal printer. Below 12 pt the two- and three-digit numerals
      begin to fill in once the image is thresholded to pure black and white.</p>
    <div class="ladder">
__LADDER__
    </div>
  </section>

  <section>
    <h2>Character map</h2>
    <p class="sub">Every route to every number. The same data is in
      <code>charmap.csv</code>.</p>
    <div class="maps">
      <div class="tablebox"><table>
        <thead><tr><th></th><th>N</th><th>Type</th><th>Byte</th><th>PUA</th><th>Unicode</th></tr></thead>
        <tbody>
__TABLE_A__
        </tbody></table></div>
      <div class="tablebox"><table>
        <thead><tr><th></th><th>N</th><th>Type</th><th>Byte</th><th>PUA</th><th>Unicode</th></tr></thead>
        <tbody>
__TABLE_B__
        </tbody></table></div>
    </div>
  </section>

  <footer>
    <div>Install <code>CircledNumbers-Regular.ttf</code>, then restart your label
      software so it re-scans the font list.</div>
    <div>SIL Open Font License 1.1. Numerals derived from Inter, Copyright 2020
      The Inter Project Authors.</div>
  </footer>

</div>

<div id="toast" role="status" aria-live="polite"></div>

<script>
(function(){
  var toast = document.getElementById('toast'), timer;
  function show(msg){
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(timer);
    timer = setTimeout(function(){ toast.classList.remove('show'); }, 1700);
  }
  document.querySelectorAll('.cell').forEach(function(btn){
    btn.addEventListener('click', function(){
      var ch = String.fromCodePoint(parseInt(btn.dataset.copy, 10));
      var label = 'Copied ' + btn.dataset.n + ' — ' + btn.dataset.note;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(ch).then(function(){ show(label); },
                                              function(){ show('Copy blocked by the browser'); });
      } else {
        show('Copy is unavailable here');
      }
    });
  });
})();
</script>
"""


if __name__ == "__main__":
    d = os.path.join(HERE, "dist")
    build(
        ttf=os.path.join(d, "CircledNumbers-Regular.ttf"),
        woff2=os.path.join(d, "CircledNumbers-Regular.woff2"),
        body_regular=sys.argv[1],
        body_semibold=sys.argv[2],
        out=sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "cheatsheet.html"),
    )
