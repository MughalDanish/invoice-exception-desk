"""Generate local-only, buildless concepts from committed synthetic public data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / 'docs/ui-ux/design-preview'
DEST.mkdir(parents=True, exist_ok=True)
data = json.loads((ROOT / 'fixtures/public-demo.json').read_text(encoding='utf-8'))
# Only the already-public synthetic projection; never read .env or private APIs.
(DEST / 'data.js').write_text('window.DEMO = ' + json.dumps(data, ensure_ascii=True) + ';\n', encoding='utf-8')
themes = [('a', 'Modern Enterprise', 'Clarity at operating speed'),
          ('b', 'Financial Intelligence', 'Every exception deserves a clear decision'),
          ('c', 'Evidence Workspace', 'Bring the evidence into focus')]
for key, name, tagline in themes:
    html = '''<!doctype html>
<html lang="en" data-theme="THEME"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>NAME | Invoice Exception Desk concept</title><link rel="stylesheet" href="concept.css"><script defer src="data.js"></script><script defer src="concept.js"></script></head>
<body><a class="skip" href="#main">Skip to content</a><div class="concept-banner"><strong>DESIGN CONCEPT / THEMEUP</strong><span>Synthetic fixture snapshot. No API connection or financial actions. Future AI is a design proposal.</span><a href="index.html">Compare themes</a></div>
<div class="shell"><aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark">ie</span><span>Invoice<br>Exception Desk</span></a><div class="workspace-name">SYNTHETIC WORKSPACE</div><nav aria-label="Concept screens"><a href="#overview">Overview</a><a href="#invoices">All invoices</a><a href="#detail">Invoice review</a><a href="#exceptions">Exception investigation</a><a href="#activity">Activity timeline</a><a href="#original">Original extraction</a><a href="#future">AI workspace <span class="nav-label">Future</span></a></nav><div class="sidebar-foot"><span class="status-dot"></span> Local design preview<p>No records can be changed.</p></div></aside>
<div class="body"><header class="topbar"><span>Accounts payable <span class="subtle">/ NAME</span></span><div class="theme-links"><a href="theme-a.html">A</a><a href="theme-b.html">B</a><a href="theme-c.html">C</a></div></header><main id="main" tabindex="-1"><div class="page-head"><div><p class="eyebrow">TAGLINE</p><h1 id="screen-title">Overview</h1><p class="subtle" id="screen-description"></p></div><span class="badge info">Static concept</span></div><div id="content"></div></main><footer>Invoice Exception Desk <span>Source: committed Phase 1 synthetic read model / 14 Nov 2026</span></footer></div></div><div id="copy-status" role="status" aria-live="polite"></div></body></html>'''
    for old, new in [('THEMEUP', key.upper()), ('THEME', key), ('NAME', name), ('TAGLINE', tagline)]:
        html = html.replace(old, new)
    (DEST / f'theme-{key}.html').write_text(html, encoding='utf-8')
print('Generated 3 independent HTML concepts and public synthetic data.js')
