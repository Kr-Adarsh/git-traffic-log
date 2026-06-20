"""
traffic visualizer — interactive dashboard for your traffic_log.csv
usage:
    python traffic_viz.py path/to/traffic_log.csv

requires: pip install plotly pandas
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# check deps before doing anything
try:
    import pandas as pd
except ImportError:
    print("pandas is required. Install it with: pip install pandas")
    sys.exit(1)

try:
    import plotly  # noqa: F401
except ImportError:
  print("plotly not installed — the script will still generate the HTML dashboard. Install it with: pip install plotly for full local plotting support")

# ── Theme
PALETTE = [
    "#10b981", "#8b5cf6", "#3b82f6", "#f59e0b", "#06b6d4",
    "#f43f5e", "#eab308", "#22c55e", "#6366f1", "#ec4899",
    "#14b8a6", "#d946ef", "#60a5fa", "#f97316", "#84cc16",
    "#c084fc", "#0ea5e9", "#fdba74", "#86efac", "#e879f9",
]


def short_name(full_name):
    return full_name.split("/")[-1] if "/" in full_name else full_name


def get_color(i):
    return PALETTE[i % len(PALETTE)]


def build_dashboard_html(df, csv_path):
    """Build a fully self-contained HTML dashboard string."""
    
    if df.empty:
        repos = []
        date_range = "No Data"
        df_min_date = ""
        df_max_date = ""
    else:
        df["date"] = df["timestamp_utc"].dt.strftime("%Y-%m-%d")
        repos = sorted(df["repo"].unique())
        df_min_date = df["date"].min()
        df_max_date = df["date"].max()
        date_range = f'{df_min_date} → {df_max_date}'

    # Pre-compute all data as JSON-serializable structures
    repo_data = {}
    for i, repo in enumerate(repos):
        rdf = df[df["repo"] == repo]

        views_daily = (
            rdf[rdf["type"] == "view"]
            .groupby("date", as_index=False)
            .agg(count=("count", "sum"), uniques=("uniques", "sum"))
            .sort_values("date")
        )
        clones_daily = (
            rdf[rdf["type"] == "clone"]
            .groupby("date", as_index=False)
            .agg(count=("count", "sum"), uniques=("uniques", "sum"))
            .sort_values("date")
        )

        repo_data[repo] = {
            "short": short_name(repo),
            "color": get_color(i),
            "views_total": int(rdf[rdf["type"] == "view"]["count"].sum()),
            "views_uniques": int(rdf[rdf["type"] == "view"]["uniques"].sum()),
            "clones_total": int(rdf[rdf["type"] == "clone"]["count"].sum()),
            "clones_uniques": int(rdf[rdf["type"] == "clone"]["uniques"].sum()),
            "views_dates": views_daily["date"].tolist(),
            "views_counts": views_daily["count"].tolist(),
            "views_unique_counts": views_daily["uniques"].tolist(),
            "clones_dates": clones_daily["date"].tolist(),
            "clones_counts": clones_daily["count"].tolist(),
            "clones_unique_counts": clones_daily["uniques"].tolist(),
        }

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Traffic Dashboard — {csv_path.stem}</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  :root {{
    --bg-dark: #050505;
    --bg-gradient: radial-gradient(circle at 50% 0%, #15151a 0%, #050505 100%);
    --surface: rgba(20, 22, 28, 0.6);
    --surface-hover: rgba(30, 32, 40, 0.8);
    --surface-2: rgba(30, 32, 40, 0.5);
    --border: rgba(255, 255, 255, 0.08);
    --border-hover: rgba(255, 255, 255, 0.15);
    --green: #10b981;
    --green-dim: rgba(16, 185, 129, 0.15);
    --purple: #8b5cf6;
    --purple-dim: rgba(139, 92, 246, 0.15);
    --blue: #3b82f6;
    --text: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --radius: 16px;
    --shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
    --glow: 0 0 20px rgba(16, 185, 129, 0.15);
  }}

  html, body {{
    height: 100%;
  }}
  body {{
    font-family: 'Inter', sans-serif;
    background: var(--bg-dark);
    background-image: var(--bg-gradient);
    color: var(--text);
    display: flex;
    flex-direction: column;
  }}
  
  .number-font {{
    font-family: 'JetBrains Mono', monospace;
  }}

  /* ── Header ── */
  .header {{
    padding: 16px 28px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
    background: rgba(10, 11, 15, 0.5);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 10;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .header h1 {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.03em;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .header h1 span {{
    color: var(--green);
  }}
  .badge-container {{
    display: flex;
    gap: 8px;
  }}
  .header-badge {{
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--surface-2);
    padding: 4px 12px;
    border-radius: 20px;
    border: 1px solid var(--border);
    backdrop-filter: blur(4px);
  }}
  
  /* ── Controls in Header ── */
  .controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  
  .btn {{
    padding: 6px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--text);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: 'Inter', sans-serif;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .btn:hover {{
    background: var(--surface-hover);
    border-color: var(--border-hover);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  }}
  .btn:active {{
    transform: translateY(0);
  }}
  .btn-primary {{
    background: var(--green-dim);
    color: var(--green);
    border-color: rgba(16, 185, 129, 0.3);
  }}
  .btn-primary:hover {{
    background: rgba(16, 185, 129, 0.25);
    border-color: rgba(16, 185, 129, 0.5);
    box-shadow: var(--glow);
  }}
  
  .date-range {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--surface-2);
    padding: 4px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }}
  .date-range span {{
    font-size: 11px;
    color: var(--text-muted);
  }}
  .date-range input {{
    background: transparent;
    border: none;
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    outline: none;
    cursor: pointer;
    color-scheme: dark;
  }}

  /* ── Layout ── */
  .layout {{
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }}

  /* ── Sidebar ── */
  .sidebar {{
    width: 280px;
    min-width: 280px;
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    background: rgba(10, 11, 15, 0.3);
    backdrop-filter: blur(10px);
    overflow: hidden;
  }}
  .sidebar-header {{
    padding: 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .sidebar-title {{
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-secondary);
  }}
  .sidebar-actions {{
    display: flex;
    gap: 8px;
  }}
  .sidebar-actions button {{
    flex: 1;
    padding: 6px 0;
    font-size: 11px;
    font-family: inherit;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface-2);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
  }}
  .sidebar-actions button:hover {{
    border-color: var(--border-hover);
    color: var(--text);
    background: var(--surface-hover);
  }}
  .sidebar-search {{
    width: 100%;
    padding: 10px 14px;
    font-size: 12px;
    font-family: inherit;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: rgba(0,0,0,0.2);
    color: var(--text);
    outline: none;
    transition: all 0.2s;
  }}
  .sidebar-search::placeholder {{
    color: var(--text-muted);
  }}
  .sidebar-search:focus {{
    border-color: var(--green);
    box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.3);
  }}
  .repo-list {{
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  
  /* Custom Scrollbar */
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.1); border-radius: 10px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.2); }}

  .repo-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    border: 1px solid transparent;
  }}
  .repo-item:hover {{
    background: var(--surface);
    border-color: rgba(255,255,255,0.05);
  }}
  .repo-item.hidden-by-search {{
    display: none;
  }}

  /* Custom checkbox */
  .repo-check {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid var(--border-hover);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }}
  .repo-item.checked .repo-check {{
    border-color: var(--color);
    background: var(--color);
  }}
  .repo-item.checked .repo-check::after {{
    content: '';
    width: 4px;
    height: 8px;
    border: solid var(--bg-dark);
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
    margin-top: -2px;
  }}

  .repo-color {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 8px var(--color);
  }}
  .repo-name {{
    font-size: 12px;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }}
  .repo-stat {{
    font-size: 11px;
    color: var(--text-secondary);
    flex-shrink: 0;
  }}

  /* ── Main content ── */
  .main {{
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px 32px 60px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }}

  /* ── Stat cards ── */
  .stats-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
  }}
  .stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent, transparent);
    opacity: 0.8;
  }}
  .stat-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px -4px rgba(0,0,0,0.5);
    border-color: var(--border-hover);
  }}
  .stat-label {{
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-secondary);
  }}
  .stat-value {{
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
  }}
  .stat-value.green {{ color: var(--green); }}
  .stat-value.purple {{ color: var(--purple); }}
  .stat-value.blue {{ color: var(--blue); }}
  .stat-sub {{
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
  }}

  /* ── Chart panels ── */
  .chart-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }}
  .chart-panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
    min-width: 0;
  }}
  .chart-panel:hover {{
    box-shadow: 0 8px 30px -4px rgba(0,0,0,0.5);
  }}
  .chart-panel.full {{
    grid-column: 1 / -1;
  }}
  .chart-header-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .chart-title {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text);
  }}
  .chart-container {{
    width: 100%;
    position: relative;
    overflow: hidden;
  }}

  /* ── Tabs ── */
  .tab-bar {{
    display: flex;
    gap: 4px;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    padding: 4px;
    width: fit-content;
    border: 1px solid var(--border);
  }}
  .tab-btn {{
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    padding: 6px 16px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }}
  .tab-btn.active {{
    background: var(--surface-hover);
    color: var(--text);
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }}
  .tab-btn:hover:not(.active) {{
    color: var(--text-secondary);
  }}

  /* ── Responsive ── */
  @media (max-width: 1024px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
  }}
  @media (max-width: 768px) {{
    .sidebar {{ width: 240px; min-width: 240px; }}
    .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
    .header {{ flex-direction: column; align-items: flex-start; }}
    .controls {{ width: 100%; justify-content: space-between; }}
  }}
  @media (max-width: 500px) {{
    .layout {{ flex-direction: column; }}
    .sidebar {{ width: 100%; min-width: 100%; max-height: 300px; border-right: none; border-bottom: 1px solid var(--border); }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1><span>traffic</span>.log</h1>
    <div class="badge-container">
      <span class="header-badge" id="badgeRepos">{len(repos)} repos</span>
      <span class="header-badge" id="badgeDates">{date_range}</span>
    </div>
  </div>
  <div class="controls">
    <label class="btn btn-primary">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
      Upload CSV
      <input type="file" id="csvFile" accept=".csv" hidden>
    </label>
    <span id="csvFileName" style="font-size: 12px; color: var(--text-muted); max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"></span>
    
    <div class="date-range">
      <input type="date" id="dateFrom">
      <span>to</span>
      <input type="date" id="dateTo">
    </div>
    <button class="btn" onclick="updateAll()">Apply</button>
    <button class="btn" style="background: transparent" onclick="resetFilters()">Reset</button>
  </div>
</div>

<div class="layout">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">Repositories</div>
      <input type="text" class="sidebar-search" id="repoSearch" placeholder="Search repositories..." oninput="filterRepoList()">
      <div class="sidebar-actions">
        <button onclick="selectAll()">All</button>
        <button onclick="selectNone()">None</button>
        <button onclick="selectTop(5)">Top 5</button>
      </div>
    </div>
    <div class="repo-list" id="repoList"></div>
  </div>

  <!-- Main -->
  <div class="main">
    <div class="stats-row">
      <div class="stat-card" style="--accent: var(--green)">
        <span class="stat-label">Total Views</span>
        <span class="stat-value number-font green" id="statViews">0</span>
        <span class="stat-sub number-font" id="statViewsSub">0 unique</span>
      </div>
      <div class="stat-card" style="--accent: var(--purple)">
        <span class="stat-label">Total Clones</span>
        <span class="stat-value number-font purple" id="statClones">0</span>
        <span class="stat-sub number-font" id="statClonesSub">0 unique</span>
      </div>
      <div class="stat-card" style="--accent: var(--blue)">
        <span class="stat-label">Active Repos</span>
        <span class="stat-value number-font blue" id="statRepos">0</span>
        <span class="stat-sub" id="statReposSub">selected</span>
      </div>
      <div class="stat-card" style="--accent: var(--text-muted)">
        <span class="stat-label">Date Range</span>
        <span class="stat-value number-font" style="font-size:18px; line-height: 1.8; color: var(--text)" id="statRange">{date_range}</span>
        <span class="stat-sub" id="statDays">&nbsp;</span>
      </div>
    </div>

    <div class="chart-panel full">
      <div class="chart-header-row">
        <span class="chart-title">Views Over Time</span>
        <div class="tab-bar">
          <button class="tab-btn active" onclick="setViewsMode('total',this)">Total</button>
          <button class="tab-btn" onclick="setViewsMode('unique',this)">Unique</button>
        </div>
      </div>
      <div class="chart-container" id="chartViews"></div>
    </div>

    <div class="chart-panel full">
      <div class="chart-header-row">
        <span class="chart-title">Clones Over Time</span>
        <div class="tab-bar">
          <button class="tab-btn active" onclick="setClonesMode('total',this)">Total</button>
          <button class="tab-btn" onclick="setClonesMode('unique',this)">Unique</button>
        </div>
      </div>
      <div class="chart-container" id="chartClones"></div>
    </div>

    <div class="chart-grid">
      <div class="chart-panel">
        <span class="chart-title">Repo Comparison</span>
        <div class="chart-container" id="chartBar"></div>
      </div>
      <div class="chart-panel">
        <span class="chart-title">Views vs Clones</span>
        <div class="chart-container" id="chartDonut"></div>
      </div>
    </div>
  </div>
</div>

<script>
// ── Data ──
let REPO_DATA = {json.dumps(repo_data)};
let REPOS = {json.dumps(repos)};
const PALETTE = {json.dumps(PALETTE)};
function get_color(i) {{ return PALETTE[i % PALETTE.length]; }}

// ── State ──
const selected = new Set(REPOS);
let viewsMode = 'total';
let clonesMode = 'total';

// ── Theme constants ──
const THEME = {{
  bg: 'transparent',
  surface: 'rgba(20,22,28,0.8)',
  border: 'rgba(255,255,255,0.08)',
  text: '#f8fafc',
  muted: '#64748b',
  sub: '#94a3b8',
  green: '#10b981',
  purple: '#8b5cf6',
}};

const CHART_LAYOUT = {{
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: {{ family: "'Inter', sans-serif", color: THEME.sub, size: 12 }},
  margin: {{ t: 20, b: 40, l: 50, r: 20 }},
  xaxis: {{
    gridcolor: THEME.border, gridwidth: 1,
    tickfont: {{ color: THEME.muted, size: 10, family: "'JetBrains Mono', monospace" }},
    linecolor: THEME.border, zerolinecolor: THEME.border,
  }},
  yaxis: {{
    gridcolor: THEME.border, gridwidth: 1,
    tickfont: {{ color: THEME.muted, size: 10, family: "'JetBrains Mono', monospace" }},
    linecolor: THEME.border, zerolinecolor: THEME.border,
  }},
  hoverlabel: {{
    bgcolor: '#1e2028',
    bordercolor: 'rgba(255,255,255,0.1)',
    font: {{ family: "'Inter', sans-serif", color: THEME.text, size: 12 }},
  }},
  showlegend: false,
}};

const PLOTLY_CONFIG = {{
  displayModeBar: false,
  responsive: true,
}};


// ── Helpers ──

function hexToRgba(hex, alpha) {{
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
}}

function sumCountsInRange(dates, counts, start, end) {{
  if (!dates || !counts) return 0;
  let sum = 0;
  for (let i = 0; i < dates.length; i++) {{
    const d = dates[i];
    if ((start && d < start) || (end && d > end)) continue;
    sum += Number(counts[i] || 0);
  }}
  return sum;
}}

function filterSeriesByRange(dates, values, start, end) {{
  const x = [], y = [];
  for (let i = 0; i < (dates || []).length; i++) {{
    const d = dates[i];
    if (!d) continue;
    if ((start && d < start) || (end && d > end)) continue;
    x.push(d);
    y.push(values[i] || 0);
  }}
  return {{ x, y }};
}}

function getSelectedRange() {{
  const s = document.getElementById('dateFrom').value || null;
  const e = document.getElementById('dateTo').value || null;
  return {{ start: s, end: e }};
}}

// ── Sidebar ──

function buildSidebar() {{
  const list = document.getElementById('repoList');
  list.innerHTML = '';
  const sorted = [...REPOS].sort((a, b) => {{
    const ta = (REPO_DATA[a].views_total||0) + (REPO_DATA[a].clones_total||0);
    const tb = (REPO_DATA[b].views_total||0) + (REPO_DATA[b].clones_total||0);
    return tb - ta;
  }});

  sorted.forEach(repo => {{
    const d = REPO_DATA[repo];
    const item = document.createElement('div');
    item.className = 'repo-item checked';
    item.dataset.repo = repo;
    item.style.setProperty('--color', d.color);
    item.innerHTML = `
      <div class="repo-check"></div>
      <div class="repo-color" style="background:${{d.color}}"></div>
      <span class="repo-name" title="${{repo}}">${{d.short}}</span>
      <span class="repo-stat number-font">${{(d.views_total||0) + (d.clones_total||0)}}</span>
    `;
    item.addEventListener('click', () => toggleRepo(repo, item));
    list.appendChild(item);
  }});
}}

function toggleRepo(repo, el) {{
  if (selected.has(repo)) {{
    selected.delete(repo);
    el.classList.remove('checked');
  }} else {{
    selected.add(repo);
    el.classList.add('checked');
  }}
  updateAll();
}}

function selectAll() {{
  REPOS.forEach(r => selected.add(r));
  document.querySelectorAll('.repo-item').forEach(el => el.classList.add('checked'));
  updateAll();
}}

function selectNone() {{
  selected.clear();
  document.querySelectorAll('.repo-item').forEach(el => el.classList.remove('checked'));
  updateAll();
}}

function selectTop(n) {{
  selected.clear();
  const sorted = [...REPOS].sort((a, b) => {{
    const ta = (REPO_DATA[a].views_total||0) + (REPO_DATA[a].clones_total||0);
    const tb = (REPO_DATA[b].views_total||0) + (REPO_DATA[b].clones_total||0);
    return tb - ta;
  }});
  sorted.slice(0, n).forEach(r => selected.add(r));
  document.querySelectorAll('.repo-item').forEach(el => {{
    el.classList.toggle('checked', selected.has(el.dataset.repo));
  }});
  updateAll();
}}

function filterRepoList() {{
  const q = document.getElementById('repoSearch').value.toLowerCase();
  document.querySelectorAll('.repo-item').forEach(el => {{
    const repo = el.dataset.repo.toLowerCase();
    el.classList.toggle('hidden-by-search', q && !repo.includes(q));
  }});
}}


// ── Stats ──

function updateStats() {{
  const range = getSelectedRange();
  let views = 0, viewsU = 0, clones = 0, clonesU = 0;
  
  selected.forEach(repo => {{
    const d = REPO_DATA[repo];
    if(!d) return;
    views += sumCountsInRange(d.views_dates, d.views_counts, range.start, range.end);
    viewsU += sumCountsInRange(d.views_dates, d.views_unique_counts, range.start, range.end);
    clones += sumCountsInRange(d.clones_dates, d.clones_counts, range.start, range.end);
    clonesU += sumCountsInRange(d.clones_dates, d.clones_unique_counts, range.start, range.end);
  }});
  
  document.getElementById('statViews').textContent = views.toLocaleString();
  document.getElementById('statViewsSub').textContent = viewsU.toLocaleString() + ' unique';
  document.getElementById('statClones').textContent = clones.toLocaleString();
  document.getElementById('statClonesSub').textContent = clonesU.toLocaleString() + ' unique';
  document.getElementById('statRepos').textContent = selected.size;
  document.getElementById('statReposSub').textContent = `of ${{REPOS.length}} total`;
  
  const rngStr = (range.start && range.end) ? `${{range.start}} → ${{range.end}}` : (range.start || range.end || 'All Time');
  document.getElementById('statRange').textContent = rngStr;
  document.getElementById('badgeDates').textContent = rngStr;
  
  if (range.start && range.end) {{
      const d1 = new Date(range.start);
      const d2 = new Date(range.end);
      const diffTime = Math.abs(d2 - d1);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
      document.getElementById('statDays').textContent = diffDays + ' days span';
  }} else {{
      document.getElementById('statDays').textContent = '—';
  }}
}}


// ── Charts ──

function renderViews() {{
  const traces = [];
  const range = getSelectedRange();
  selected.forEach(repo => {{
    const d = REPO_DATA[repo];
    if(!d) return;
    const y = viewsMode === 'unique' ? d.views_unique_counts : d.views_counts;
    const f = filterSeriesByRange(d.views_dates, y, range.start, range.end);
    traces.push({{
      x: f.x, y: f.y, name: d.short, mode: 'lines+markers',
      line: {{ color: d.color, width: 2.5, shape: 'linear' }},
      marker: {{ color: d.color, size: 6, opacity: 0 }},
      fill: 'tozeroy',
      fillcolor: d.color.startsWith('#') ? hexToRgba(d.color, 0.05) : 'transparent',
      opacity: 0.9,
      hovertemplate: `<b>${{d.short}}</b><br>%{{x}}<br>${{viewsMode === 'unique' ? 'Unique' : 'Views'}}: %{{y}}<extra></extra>`,
    }});
  }});
  const layout = {{ ...CHART_LAYOUT, height: 320,
    yaxis: {{ ...CHART_LAYOUT.yaxis, title: {{ text: viewsMode === 'unique' ? 'Unique Visitors' : 'Views', font: {{ color: THEME.muted, size: 11 }} }} }},
  }};
  Plotly.react('chartViews', traces, layout, PLOTLY_CONFIG);
}}

function renderClones() {{
  const traces = [];
  const range = getSelectedRange();
  selected.forEach(repo => {{
    const d = REPO_DATA[repo];
    if(!d) return;
    const y = clonesMode === 'unique' ? d.clones_unique_counts : d.clones_counts;
    const f = filterSeriesByRange(d.clones_dates, y, range.start, range.end);
    traces.push({{
      x: f.x, y: f.y, name: d.short, mode: 'lines+markers',
      line: {{ color: d.color, width: 2.5, shape: 'linear' }},
      marker: {{ color: d.color, size: 6, opacity: 0 }},
      fill: 'tozeroy',
      fillcolor: d.color.startsWith('#') ? hexToRgba(d.color, 0.05) : 'transparent',
      opacity: 0.9,
      hovertemplate: `<b>${{d.short}}</b><br>%{{x}}<br>${{clonesMode === 'unique' ? 'Unique' : 'Clones'}}: %{{y}}<extra></extra>`,
    }});
  }});
  const layout = {{ ...CHART_LAYOUT, height: 300,
    yaxis: {{ ...CHART_LAYOUT.yaxis, title: {{ text: clonesMode === 'unique' ? 'Unique Cloners' : 'Clones', font: {{ color: THEME.muted, size: 11 }} }} }},
  }};
  Plotly.react('chartClones', traces, layout, PLOTLY_CONFIG);
}}

function renderBar() {{
  const range = getSelectedRange();
  const repos = [...selected].sort((a, b) => {{
    const va = sumCountsInRange((REPO_DATA[a]||{{}}).views_dates, (REPO_DATA[a]||{{}}).views_counts, range.start, range.end) || 0;
    const vb = sumCountsInRange((REPO_DATA[b]||{{}}).views_dates, (REPO_DATA[b]||{{}}).views_counts, range.start, range.end) || 0;
    return vb - va;
  }});
  
  const names = repos.map(r => (REPO_DATA[r]||{{}}).short);
  const viewsVals = repos.map(r => sumCountsInRange((REPO_DATA[r]||{{}}).views_dates, (REPO_DATA[r]||{{}}).views_counts, range.start, range.end) || 0);
  const clonesVals = repos.map(r => sumCountsInRange((REPO_DATA[r]||{{}}).clones_dates, (REPO_DATA[r]||{{}}).clones_counts, range.start, range.end) || 0);

  const maxLabelChars = names.reduce((m, n) => Math.max(m, (n || '').length), 0);
  const leftMargin = Math.min(320, 60 + maxLabelChars * 7);
  const allVals = viewsVals.concat(clonesVals);
  const maxValLen = allVals.length ? Math.max(...allVals.map(v => String(v).length)) : 1;
  const rightMargin = Math.min(160, 30 + maxValLen * 10);

  const traces = [
    {{
      y: names, x: viewsVals, text: viewsVals.map(v => v.toLocaleString()),
      textposition: 'outside', textfont: {{ color: THEME.text, size: 11, family: "'JetBrains Mono', monospace" }},
      name: 'Views', type: 'bar', orientation: 'h',
      marker: {{ color: THEME.green, opacity: 0.9, line: {{ width: 0 }} }},
      hovertemplate: '<b>%{{y}}</b><br>Views: %{{text}}<extra></extra>',
      cliponaxis: false,
    }},
    {{
      y: names, x: clonesVals, text: clonesVals.map(v => v.toLocaleString()),
      textposition: 'outside', textfont: {{ color: THEME.text, size: 11, family: "'JetBrains Mono', monospace" }},
      name: 'Clones', type: 'bar', orientation: 'h',
      marker: {{ color: THEME.purple, opacity: 0.9, line: {{ width: 0 }} }},
      hovertemplate: '<b>%{{y}}</b><br>Clones: %{{text}}<extra></extra>',
      cliponaxis: false,
    }},
  ];
  const h = Math.max(250, repos.length * 36 + 80);
  const layout = {{
    ...CHART_LAYOUT,
    height: h,
    barmode: 'group',
    bargap: 0.2,
    bargroupgap: 0.1,
    showlegend: true,
    legend: {{
      font: {{ color: THEME.text, size: 11 }},
      bgcolor: 'rgba(0,0,0,0.2)',
      bordercolor: THEME.border, borderwidth: 1,
      orientation: 'h', x: 0.5, y: 1.1, xanchor: 'center'
    }},
    yaxis: {{
      ...CHART_LAYOUT.yaxis,
      automargin: true, autorange: 'reversed',
      tickfont: {{ color: THEME.sub, size: 11 }},
    }},
    xaxis: {{
      ...CHART_LAYOUT.xaxis,
      type: 'linear', tickformat: ',',
      title: {{ text: 'Count', font: {{ color: THEME.muted, size: 11 }} }},
    }},
    margin: {{ t: 40, b: 40, l: leftMargin, r: rightMargin }},
  }};
  Plotly.react('chartBar', traces, layout, PLOTLY_CONFIG);
}}

function renderDonut() {{
  const range = getSelectedRange();
  let views = 0, clones = 0;
  selected.forEach(repo => {{
    const d = REPO_DATA[repo];
    if(!d) return;
    views += sumCountsInRange(d.views_dates, d.views_counts, range.start, range.end);
    clones += sumCountsInRange(d.clones_dates, d.clones_counts, range.start, range.end);
  }});
  
  const traces = [{{ 
    labels: ['Views', 'Clones'], 
    values: [views, clones], 
    type: 'pie', 
    hole: 0.65, 
    textinfo: 'percent', 
    textposition: 'inside', 
    insidetextfont: {{ color: '#fff', family: "'JetBrains Mono', monospace", size: 13, weight: 600 }}, 
    marker: {{ colors: [THEME.green, THEME.purple], line: {{ color: '#0A0B0F', width: 4 }} }}, 
    hovertemplate: '<b>%{{label}}</b><br>%{{value:,}} (%{{percent}})<extra></extra>' 
  }}];
  
  const containerEl = document.getElementById('chartDonut');
  const width = containerEl ? containerEl.clientWidth : 380;
  const height = Math.max(250, Math.min(380, Math.round(width * 0.7)));
  
  const layout = {{
    ...CHART_LAYOUT, 
    height: height, 
    margin: {{ t: 20, b: 20, l: 20, r: 20 }}, 
    annotations: [{{ 
      text: `<b style="color:${{THEME.text}}">${{(views + clones).toLocaleString()}}</b><br><span style="font-size:11px;color:${{THEME.muted}}">TOTAL</span>`, 
      showarrow: false, 
      font: {{ size: 24, family: "'JetBrains Mono', monospace" }} 
    }}] 
  }};
  Plotly.react('chartDonut', traces, layout, PLOTLY_CONFIG);
}}


// ── Tab handlers ──

function setViewsMode(mode, btn) {{
  viewsMode = mode;
  btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderViews();
}}

function setClonesMode(mode, btn) {{
  clonesMode = mode;
  btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderClones();
}}


// ── Update everything ──

function updateAll() {{
  updateStats();
  renderViews();
  renderClones();
  renderBar();
  renderDonut();
}}

// ── Reset & Init ──

function resetFilters() {{
  const allDates = [];
  Object.values(REPO_DATA).forEach(d => {{ 
      allDates.push(...(d.views_dates || [])); 
      allDates.push(...(d.clones_dates || [])); 
  }});
  const uniq = [...new Set(allDates)].sort();
  if (uniq.length) {{ 
      document.getElementById('dateFrom').value = uniq[0]; 
      document.getElementById('dateTo').value = uniq[uniq.length - 1]; 
  }}
  selectAll();
}}

function initDates() {{
  const allDates = [];
  Object.values(REPO_DATA).forEach(d => {{ 
      allDates.push(...(d.views_dates || [])); 
      allDates.push(...(d.clones_dates || [])); 
  }});
  const uniq = [...new Set(allDates)].sort();
  if (uniq.length) {{
    const last = uniq[uniq.length - 1];
    const lastDate = new Date(last);
    const startDate = new Date(lastDate);
    startDate.setDate(startDate.getDate() - 30);
    const startISO = startDate.toISOString().slice(0,10);
    const minDate = uniq[0];
    document.getElementById('dateFrom').value = startISO < minDate ? minDate : startISO;
    document.getElementById('dateTo').value = last;
  }} else {{
    const today = new Date();
    const end = today.toISOString().slice(0,10);
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 30);
    document.getElementById('dateFrom').value = startDate.toISOString().slice(0,10);
    document.getElementById('dateTo').value = end;
  }}
}}

// ── File Upload CSV Parser ──

document.getElementById('csvFile').addEventListener('change', function(e) {{
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  document.getElementById('csvFileName').textContent = f.name;
  
  Papa.parse(f, {{ 
    header: true, dynamicTyping: true, skipEmptyLines: true, 
    complete: function(results) {{
      try {{
        const rows = results.data;
        const byRepo = {{}};
        let minDate = null, maxDate = null;
        
        rows.forEach(r => {{
          const repo = r.repo || 'unknown';
          const type = (r.type || '').toLowerCase();
          const count = Number(r.count) || 0;
          const uniques = Number(r.uniques) || 0;
          let ts = r.timestamp_utc || r.captured_at_utc || r.timestamp || '';
          let d = new Date(ts);
          if (isNaN(d)) d = new Date(ts.replace(' ', 'T') + 'Z');
          const dateStr = isNaN(d) ? '' : d.toISOString().slice(0, 10);
          
          if (dateStr) {{
            if (!minDate || dateStr < minDate) minDate = dateStr;
            if (!maxDate || dateStr > maxDate) maxDate = dateStr;
          }}
          if (!byRepo[repo]) byRepo[repo] = {{ items: [] }};
          byRepo[repo].items.push({{ date: dateStr, type, count, uniques }});
        }});

        const newRepoData = {{}};
        const newRepos = Object.keys(byRepo).sort();
        
        newRepos.forEach((repo, i) => {{
          const list = byRepo[repo].items;
          const viewsMap = {{}}, clonesMap = {{}};
          
          list.forEach(it => {{
            const d = it.date;
            if (!d) return;
            if (it.type === 'view') {{
              if (!viewsMap[d]) viewsMap[d] = {{ count: 0, uniques: 0 }};
              viewsMap[d].count += it.count;
              viewsMap[d].uniques += it.uniques;
            }} else if (it.type === 'clone') {{
              if (!clonesMap[d]) clonesMap[d] = {{ count: 0, uniques: 0 }};
              clonesMap[d].count += it.count;
              clonesMap[d].uniques += it.uniques;
            }}
          }});

          const vDates = Object.keys(viewsMap).sort(), cDates = Object.keys(clonesMap).sort();
          
          newRepoData[repo] = {{
            short: repo.split('/').pop() || repo,
            color: get_color(i),
            views_total: vDates.reduce((a, b) => a + viewsMap[b].count, 0),
            views_uniques: vDates.reduce((a, b) => a + viewsMap[b].uniques, 0),
            clones_total: cDates.reduce((a, b) => a + clonesMap[b].count, 0),
            clones_uniques: cDates.reduce((a, b) => a + clonesMap[b].uniques, 0),
            views_dates: vDates,
            views_counts: vDates.map(d => viewsMap[d].count),
            views_unique_counts: vDates.map(d => viewsMap[d].uniques),
            clones_dates: cDates,
            clones_counts: cDates.map(d => clonesMap[d].count),
            clones_unique_counts: cDates.map(d => clonesMap[d].uniques),
          }};
        }});

        REPO_DATA = newRepoData;
        REPOS = newRepos;
        document.getElementById('badgeRepos').textContent = `${{REPOS.length}} repos`;
        
        selected.clear();
        REPOS.forEach(r => selected.add(r));
        
        buildSidebar();
        initDates();
        updateAll();
        
      }} catch (err) {{
        console.error('Error processing uploaded CSV', err);
        alert('Error processing uploaded CSV — see console for details');
      }}
    }}
  }});
}});

// ── Start ──
buildSidebar();
if(REPOS.length > 0) {{
    initDates();
    updateAll();
}} else {{
    document.getElementById('statRange').textContent = 'No Data';
}}
</script>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="GitHub Traffic Dashboard")
    parser.add_argument("csv", nargs="?", default="traffic_log.csv", help="Path to traffic_log.csv")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
      print(f"[!] File not found: {csv_path} — generating empty dashboard. Upload CSV from browser to populate data.")
      # create an empty dataframe with the expected columns and datetime dtypes
      df = pd.DataFrame({
        "timestamp_utc": pd.to_datetime([], utc=True),
        "captured_at_utc": pd.to_datetime([], utc=True),
        "type": pd.Series(dtype="object"),
        "count": pd.Series(dtype="int64"),
        "uniques": pd.Series(dtype="int64"),
        "repo": pd.Series(dtype="object"),
      })
    else:
      df = pd.read_csv(csv_path, parse_dates=["timestamp_utc", "captured_at_utc"])
      print(f"[✓] Loaded {len(df)} rows from {csv_path}")

    if not df.empty and "repo" not in df.columns:
        print("[i] Old CSV format (no 'repo' column) — treating as single repo")
        df["repo"] = "unknown"

    if not df.empty:
        repos = sorted(df["repo"].unique())
        print(f"[i] Repos: {', '.join(repos)}")

    html = build_dashboard_html(df, csv_path)

    out = csv_path.parent / "traffic_dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"[✓] Saved dashboard → {out}")

    # Try to open in browser
    import webbrowser
    webbrowser.open(str(out.resolve()))


if __name__ == "__main__":
    main()