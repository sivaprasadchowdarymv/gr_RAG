"""
Custom CSS for the parts Streamlit doesn't style itself (answer box,
citation popups, source excerpts, metric meters). Base colours come from
.streamlit/config.toml so native widgets match.

Palette ("datasheet paper"):
    ink      #17202B   body text
    paper    #FFFFFF   page
    panel    #F3F6F9   cards, sidebar
    rule     #D5DCE4   borders / graph-paper grid
    muted    #5B6878   secondary text
    trace    #1D5FB8   schematic blue: links, citations, focus
Type: IBM Plex Sans for the interface, IBM Plex Mono only for raw datasheet
excerpts (where column alignment matters). Falls back to system fonts offline.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink: #17202B; --paper: #FFFFFF; --panel: #F3F6F9; --rule: #D5DCE4;
  --muted: #5B6878; --trace: #1D5FB8; --trace-soft: #E8F0FB;
  --ok: #1C7C4A; --warn: #A86B0C; --bad: #B83A2E;
  --sans: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace;
}
html, body, .stApp, .stMarkdown, button, input, textarea { font-family: var(--sans); }
.block-container { padding-top: 2rem; max-width: 1100px; }
h1, h2, h3 { color: var(--ink); font-weight: 600; letter-spacing: -0.01em; }

/* Header: the one distinctive element, a strip of engineering graph paper */
.app-header {
  border: 1px solid var(--rule); border-radius: 6px; padding: 1.4rem 1.6rem;
  background-color: var(--paper);
  background-image:
    linear-gradient(var(--rule) 1px, transparent 1px),
    linear-gradient(90deg, var(--rule) 1px, transparent 1px);
  background-size: 22px 22px; background-position: -1px -1px;
  margin-bottom: 1.4rem;
}
.app-header-inner { background: var(--paper); display: inline-block; padding: .4rem .8rem .5rem; border-radius: 4px; }
.app-header .app-title { font-size: 2rem !important; font-weight: 600; color: var(--ink); margin: 0; line-height: 1.2; }
.app-header .app-sub { color: var(--muted); margin: .25rem 0 0; font-size: .95rem; max-width: 60ch; }

/* Document summary */
.doc-name { font-weight: 600; color: var(--ink); font-size: 1.05rem; word-break: break-all; }
.doc-stats { display: flex; flex-wrap: wrap; gap: .5rem 1.6rem; margin-top: .4rem; color: var(--muted); font-size: .92rem; }
.doc-stats b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }

/* Answer */
.answer-box {
  background: var(--paper); border: 1px solid var(--rule); border-left: 3px solid var(--trace);
  border-radius: 6px; padding: 1.1rem 1.3rem; font-size: 1rem; line-height: 1.85;
  color: var(--ink); max-width: 80ch;
}
.answer-meta { color: var(--muted); font-size: .85rem; margin-top: .35rem; }

/* Citation badge = a reference tag on a schematic */
.cite-wrap { position: relative; display: inline-block; outline: none; }
.cite-badge {
  display: inline-block; background: var(--trace-soft); color: var(--trace);
  border: 1px solid var(--trace); border-radius: 3px; padding: 0 6px; margin: 0 2px;
  font-size: .76rem; font-weight: 600; line-height: 1.5; vertical-align: 1px;
  font-variant-numeric: tabular-nums; cursor: help; white-space: nowrap;
}
.cite-wrap:focus .cite-badge, .cite-wrap:hover .cite-badge { background: var(--trace); color: #fff; }
.cite-popup {
  display: none; position: absolute; bottom: calc(100% + 8px); left: 50%;
  transform: translateX(-50%); width: min(460px, 86vw); z-index: 9999;
  background: var(--paper); border: 1px solid var(--trace); border-radius: 6px;
  padding: .7rem .85rem; box-shadow: 0 10px 28px rgba(23, 32, 43, .18);
  font-size: .84rem; line-height: 1.5; color: var(--ink); text-align: left;
}
.cite-wrap:hover .cite-popup, .cite-wrap:focus .cite-popup, .cite-wrap:focus-within .cite-popup { display: block; }
.pop-head { font-weight: 600; margin-bottom: .15rem; }
.pop-sub { color: var(--muted); font-size: .78rem; margin-bottom: .45rem; }
.pop-body, .src-body {
  font-family: var(--mono); font-size: .8rem; white-space: pre-wrap; word-break: break-word;
  background: var(--panel); border-radius: 4px; padding: .5rem .65rem; color: var(--ink);
}
.pop-body { max-height: 190px; overflow-y: auto; }
.chip { display: inline-block; background: var(--panel); border: 1px solid var(--rule); border-radius: 3px;
        padding: 0 6px; margin: 0 4px 4px 0; font-size: .74rem; color: var(--muted); }

/* Sources */
.src-meta { color: var(--muted); font-size: .85rem; margin-bottom: .4rem; }

/* Metrics */
.metrics { margin-bottom: 1rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .75rem; }
.metric { border: 1px solid var(--rule); border-radius: 6px; padding: .65rem .8rem; background: var(--paper); }
.metric-name { color: var(--muted); font-size: .8rem; }
.metric-val { font-size: 1.35rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.meter { background: var(--panel); height: 5px; border-radius: 3px; margin-top: .3rem; overflow: hidden; }
.meter > span { display: block; height: 100%; }
.metric-tip { color: var(--muted); font-size: .72rem; margin-top: .3rem; }

/* Status lines in the sidebar */
.status-line { font-size: .9rem; margin: .1rem 0; }
.dot { display: inline-block; width: .55rem; height: .55rem; border-radius: 50%; margin-right: .45rem; vertical-align: 1px; }
.dot.ok { background: var(--ok); } .dot.bad { background: var(--bad); } .dot.warn { background: var(--warn); }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""
