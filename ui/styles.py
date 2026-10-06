"""
Theme-neutral CSS for custom elements (works in Streamlit light AND dark mode):
colours use transparency over the theme background instead of fixed whites.
Native widgets follow the theme from .streamlit/config.toml / the viewer's choice.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root { --trace: #2F6FD0; --ok: #1F9D55; --warn: #C27C0E; --bad: #D64545;
        --rule: rgba(128,128,128,.28); --tint: rgba(47,111,208,.10); --soft: rgba(128,128,128,.08);
        --sans: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
        --mono: 'IBM Plex Mono', ui-monospace, Consolas, monospace; }
html, body, .stApp, .stMarkdown, button, input, textarea { font-family: var(--sans); }
.block-container { padding-top: 1.6rem; max-width: 1150px; }
.brand { display:flex; align-items:baseline; gap:.6rem; margin-bottom:.2rem; }
.brand-title { font-size: 1.55rem; font-weight: 600; letter-spacing: -0.01em; }
.brand-sub { opacity: .7; font-size: .92rem; }
.card { border: 1px solid var(--rule); border-radius: 10px; padding: .9rem 1rem; background: var(--soft); height: 100%; }
.card-title { font-weight: 600; word-break: break-all; margin-bottom: .35rem; }
.card-row { display:flex; flex-wrap: wrap; gap: .25rem 1rem; font-size: .88rem; opacity: .85; }
.card-row b { font-variant-numeric: tabular-nums; }
.pill { display:inline-block; border-radius: 999px; padding: .05rem .55rem; font-size: .75rem; font-weight: 600;
        border: 1px solid var(--rule); margin-right: .3rem; }
.pill.ok { color: var(--ok); border-color: var(--ok); } .pill.warn { color: var(--warn); border-color: var(--warn); }
.pill.bad { color: var(--bad); border-color: var(--bad); } .pill.info { color: var(--trace); border-color: var(--trace); }
.status-line { font-size: .88rem; margin: .12rem 0; }
.dot { display:inline-block; width:.55rem; height:.55rem; border-radius:50%; margin-right:.45rem; vertical-align: 1px; }
.dot.ok { background: var(--ok); } .dot.bad { background: var(--bad); } .dot.warn { background: var(--warn); }
.src-body { font-family: var(--mono); font-size: .8rem; white-space: pre-wrap; word-break: break-word;
            background: var(--soft); border-radius: 6px; padding: .55rem .7rem; }
.src-meta { opacity: .75; font-size: .84rem; margin-bottom: .35rem; }
.metrics { display:grid; grid-template-columns: repeat(auto-fit, minmax(140px,1fr)); gap:.6rem; margin-bottom: .8rem; }
.metric { border:1px solid var(--rule); border-radius:8px; padding:.55rem .7rem; }
.metric-name { opacity:.7; font-size:.78rem; } .metric-val { font-size:1.25rem; font-weight:600; font-variant-numeric: tabular-nums; }
.meter { background: var(--soft); height:5px; border-radius:3px; margin-top:.3rem; overflow:hidden; }
.meter > span { display:block; height:100%; }
.trace-line { font-size:.88rem; margin:.1rem 0; }
.chip { display:inline-block; background: var(--tint); border:1px solid var(--trace); color: var(--trace);
        border-radius: 4px; padding: 0 .45rem; margin: 0 .3rem .3rem 0; font-size: .78rem; font-weight: 600; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""
