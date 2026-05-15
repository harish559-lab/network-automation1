"""
generate_dashboard.py
Generates a fully self-contained NETAUTO test dashboard HTML file.
All CSS, fonts (base64), and JS (Chart.js inline) are embedded — works under Jenkins CSP.

Usage:
    python generate_dashboard.py --results results.json --output reports/dashboard.html

Or call generate_dashboard(data) directly from your test runner.
"""

import json
import argparse
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Tiny subset of Chart.js v4 replaced by a hand-rolled SVG donut renderer
# so we have zero external dependencies.
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>NETAUTO Test Dashboard</title>
<style>
/* ── Reset ── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}

/* ── Tokens ── */
:root{{
  --bg:#0d1117;
  --surface:#161b22;
  --surface2:#21262d;
  --border:#30363d;
  --text:#e6edf3;
  --muted:#8b949e;
  --pass:#3fb950;
  --fail:#f85149;
  --error:#d29922;
  --skip:#58a6ff;
  --accent:#58a6ff;
  --radius:10px;
  --mono:'Courier New',monospace;
  --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}}

body{{
  background:var(--bg);
  color:var(--text);
  font-family:var(--sans);
  font-size:14px;
  line-height:1.6;
  min-height:100vh;
}}

/* ── Layout ── */
.shell{{max-width:1100px;margin:0 auto;padding:32px 20px 60px}}

/* ── Header ── */
.header{{
  display:flex;align-items:center;gap:16px;
  border-bottom:1px solid var(--border);
  padding-bottom:24px;margin-bottom:32px;
}}
.logo{{
  width:44px;height:44px;border-radius:8px;
  background:linear-gradient(135deg,#1f6feb,var(--accent));
  display:flex;align-items:center;justify-content:center;
  font-size:22px;flex-shrink:0;
}}
.header-title{{font-size:22px;font-weight:700;letter-spacing:-.5px}}
.header-sub{{font-size:12px;color:var(--muted);margin-top:2px}}
.build-badge{{
  margin-left:auto;
  background:var(--pass);color:#000;
  font-size:11px;font-weight:700;letter-spacing:.5px;
  padding:4px 12px;border-radius:20px;text-transform:uppercase;
}}
.build-badge.fail{{background:var(--fail);color:#fff}}

/* ── Metric cards ── */
.metrics{{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:16px;margin-bottom:32px;
}}
.metric{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px 18px;
  position:relative;overflow:hidden;
}}
.metric::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:var(--c,var(--accent));
}}
.metric-label{{font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:.8px;color:var(--muted);margin-bottom:8px}}
.metric-value{{font-size:36px;font-weight:700;line-height:1;font-family:var(--mono)}}
.metric-sub{{font-size:11px;color:var(--muted);margin-top:6px}}

/* ── Two-column middle section ── */
.mid{{display:grid;grid-template-columns:1fr 340px;gap:20px;margin-bottom:32px}}
@media(max-width:720px){{.mid{{grid-template-columns:1fr}}}}

/* ── Info table ── */
.card{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;
}}
.card-head{{
  padding:14px 18px;font-size:12px;font-weight:700;
  text-transform:uppercase;letter-spacing:.6px;color:var(--muted);
  border-bottom:1px solid var(--border);background:var(--surface2);
}}
.info-table{{width:100%;border-collapse:collapse}}
.info-table tr+tr td{{border-top:1px solid var(--border)}}
.info-table td{{padding:10px 18px;font-size:13px}}
.info-table td:first-child{{color:var(--muted);width:38%;font-size:12px}}
.info-table td:last-child{{font-family:var(--mono);font-size:12px}}

/* ── Donut chart ── */
.donut-wrap{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:20px;
  display:flex;flex-direction:column;align-items:center;gap:16px;
}}
.donut-wrap svg{{overflow:visible}}
.donut-legend{{display:flex;flex-wrap:wrap;gap:10px 18px;justify-content:center}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:12px}}
.legend-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}

/* ── Progress bar ── */
.progress-section{{margin-bottom:32px}}
.progress-label{{
  display:flex;justify-content:space-between;
  font-size:12px;margin-bottom:8px;
}}
.progress-track{{
  height:10px;background:var(--surface2);border-radius:20px;overflow:hidden;
  border:1px solid var(--border);
}}
.progress-fill{{
  height:100%;border-radius:20px;
  background:linear-gradient(90deg,#1f6feb,var(--pass));
  transition:width .8s ease;
}}

/* ── TC cards ── */
.tc-section-head{{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:16px;
}}
.tc-section-head h2{{font-size:14px;font-weight:700;text-transform:uppercase;
  letter-spacing:.6px;color:var(--muted)}}
.filter-tabs{{display:flex;gap:6px}}
.ftab{{
  border:1px solid var(--border);background:transparent;
  color:var(--muted);font-size:11px;font-weight:600;
  padding:4px 12px;border-radius:20px;cursor:pointer;
  text-transform:uppercase;letter-spacing:.4px;
}}
.ftab.active,.ftab:hover{{
  background:var(--accent);color:#000;border-color:var(--accent);
}}
.tc-grid{{display:flex;flex-direction:column;gap:12px}}

.tc-card{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);overflow:hidden;
  border-left:4px solid var(--tc-color,var(--border));
  transition:transform .15s;
}}
.tc-card:hover{{transform:translateX(3px)}}
.tc-header{{
  display:flex;align-items:center;gap:12px;
  padding:12px 16px;cursor:pointer;
}}
.tc-icon{{
  width:28px;height:28px;border-radius:6px;flex-shrink:0;
  background:var(--tc-color);
  display:flex;align-items:center;justify-content:center;
  font-size:14px;color:#000;font-weight:700;
}}
.tc-name{{font-weight:600;font-size:13px;flex:1}}
.tc-status-pill{{
  font-size:10px;font-weight:700;letter-spacing:.6px;
  padding:3px 10px;border-radius:20px;text-transform:uppercase;
  background:var(--tc-color);color:#000;
}}
.tc-body{{
  padding:0 16px 14px 16px;
  border-top:1px solid var(--border);
  font-size:12px;
}}
.tc-desc{{color:var(--muted);margin:10px 0 10px}}
.steps{{display:flex;flex-direction:column;gap:4px}}
.step{{
  display:flex;align-items:center;gap:8px;
  padding:6px 10px;border-radius:6px;
  background:var(--surface2);font-family:var(--mono);font-size:11px;
}}
.step-icon{{font-size:13px;flex-shrink:0}}
.step.PASSED{{border-left:3px solid var(--pass)}}
.step.FAILED{{border-left:3px solid var(--fail)}}
.step.ERRORED{{border-left:3px solid var(--error)}}
.step.BLOCKED{{border-left:3px solid var(--muted)}}

.tc-card[data-status="PASSED"]{{--tc-color:var(--pass)}}
.tc-card[data-status="FAILED"]{{--tc-color:var(--fail)}}
.tc-card[data-status="ERRORED"]{{--tc-color:var(--error)}}
.tc-card[data-status="SKIPPED"]{{--tc-color:var(--skip)}}

/* ── Footer ── */
.footer{{
  margin-top:48px;border-top:1px solid var(--border);
  padding-top:16px;text-align:center;
  font-size:11px;color:var(--muted);
}}
</style>
</head>
<body>
<div class="shell">

  <!-- HEADER -->
  <div class="header">
    <div class="logo">🧪</div>
    <div>
      <div class="header-title">NETAUTO TEST DASHBOARD</div>
      <div class="header-sub">RUN: {run_time} &nbsp;|&nbsp; Branch: {branch} &nbsp;|&nbsp; Job: {jenkins_job}</div>
    </div>
    <div class="build-badge {build_class}">{build_status}</div>
  </div>

  <!-- METRIC CARDS -->
  <div class="metrics">
    <div class="metric" style="--c:var(--accent)">
      <div class="metric-label">Total</div>
      <div class="metric-value">{total}</div>
      <div class="metric-sub">test cases</div>
    </div>
    <div class="metric" style="--c:var(--pass)">
      <div class="metric-label">Passed</div>
      <div class="metric-value" style="color:var(--pass)">{passed}</div>
      <div class="metric-sub">✓ success</div>
    </div>
    <div class="metric" style="--c:var(--fail)">
      <div class="metric-label">Failed</div>
      <div class="metric-value" style="color:var(--fail)">{failed}</div>
      <div class="metric-sub">✗ failure</div>
    </div>
    <div class="metric" style="--c:var(--error)">
      <div class="metric-label">Errored</div>
      <div class="metric-value" style="color:var(--error)">{errored}</div>
      <div class="metric-sub">⚠ error</div>
    </div>
    <div class="metric" style="--c:var(--skip)">
      <div class="metric-label">Skipped</div>
      <div class="metric-value" style="color:var(--skip)">{skipped}</div>
      <div class="metric-sub">— skipped</div>
    </div>
    <div class="metric" style="--c:var(--pass)">
      <div class="metric-label">Success Rate</div>
      <div class="metric-value" style="color:var(--pass)">{success_rate}%</div>
      <div class="metric-sub">pass / total</div>
    </div>
  </div>

  <!-- MIDDLE: info + donut -->
  <div class="mid">
    <div class="card">
      <div class="card-head">Pipeline Info</div>
      <table class="info-table">
        <tr><td>Device</td><td>{device}</td></tr>
        <tr><td>Test Module</td><td>{test_module}</td></tr>
        <tr><td>MAC Aging Time</td><td>{mac_aging_time}</td></tr>
        <tr><td>Interface</td><td>{interface}</td></tr>
        <tr><td>Jenkins Job</td><td>{jenkins_job}</td></tr>
        <tr><td>Branch</td><td>{branch}</td></tr>
      </table>
    </div>

    <div class="donut-wrap">
      <div class="card-head" style="width:100%;border-radius:6px 6px 0 0;background:var(--surface2);border:1px solid var(--border);border-bottom:none">Result Breakdown</div>
      {donut_svg}
      <div class="donut-legend">
        <div class="legend-item"><div class="legend-dot" style="background:var(--pass)"></div> Passed ({passed})</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--fail)"></div> Failed ({failed})</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--error)"></div> Errored ({errored})</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--skip)"></div> Skipped ({skipped})</div>
      </div>
    </div>
  </div>

  <!-- PROGRESS -->
  <div class="progress-section">
    <div class="progress-label">
      <span>Overall Success Rate</span>
      <span style="color:var(--pass);font-weight:700">{success_rate}%</span>
    </div>
    <div class="progress-track">
      <div class="progress-fill" style="width:{success_rate}%"></div>
    </div>
  </div>

  <!-- TEST CASES -->
  <div class="tc-section-head">
    <h2>Test Cases</h2>
    <div class="filter-tabs">
      <button class="ftab active" onclick="filter('ALL',this)">ALL</button>
      <button class="ftab" onclick="filter('PASSED',this)">Passed</button>
      <button class="ftab" onclick="filter('FAILED',this)">Failed</button>
      <button class="ftab" onclick="filter('ERRORED',this)">Errored</button>
      <button class="ftab" onclick="filter('SKIPPED',this)">Skipped</button>
    </div>
  </div>

  <div class="tc-grid" id="tcGrid">
    {tc_cards}
  </div>

  <div class="footer">
    Generated by NETAUTO &nbsp;·&nbsp; {run_time}
  </div>

</div>
<script>
function filter(status, btn) {{
  document.querySelectorAll('.ftab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.tc-card').forEach(c => {{
    c.style.display = (status === 'ALL' || c.dataset.status === status) ? '' : 'none';
  }});
}}
document.querySelectorAll('.tc-header').forEach(h => {{
  h.addEventListener('click', () => {{
    const body = h.nextElementSibling;
    if (body) body.style.display = body.style.display === 'none' ? '' : 'none';
  }});
}});
</script>
</body>
</html>
"""

STEP_ICONS = {
    "PASSED": "✓",
    "FAILED": "✗",
    "ERRORED": "⚠",
    "BLOCKED": "◌",
    "SKIPPED": "—",
}


def make_donut_svg(passed, failed, errored, skipped, total):
    """Pure SVG donut — no external library needed."""
    colors = ["#3fb950", "#f85149", "#d29922", "#58a6ff"]
    values = [passed, failed, errored, skipped]
    labels = ["Passed", "Failed", "Errored", "Skipped"]

    if total == 0:
        # grey empty ring
        return (
            '<svg width="180" height="180" viewBox="0 0 180 180">'
            '<circle cx="90" cy="90" r="70" fill="none" stroke="#30363d" stroke-width="24"/>'
            '<text x="90" y="96" text-anchor="middle" fill="#8b949e" font-size="14">No data</text>'
            "</svg>"
        )

    cx, cy, r, sw = 90, 90, 62, 26
    circumference = 2 * 3.14159265 * r
    offset = -3.14159265 / 2 * r * 2  # start at top

    segments = []
    current_angle = -90  # degrees, start top
    for i, val in enumerate(values):
        if val == 0:
            continue
        fraction = val / total
        dash = fraction * circumference
        gap = circumference - dash
        # rotate transform
        rotate = current_angle
        seg = (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{colors[i]}" stroke-width="{sw}" '
            f'stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{circumference/4:.2f}" '  # CSS trick: start at top
            f'transform="rotate({rotate} {cx} {cy})" '
            f'stroke-linecap="butt"/>'
        )
        segments.append(seg)
        current_angle += fraction * 360

    # centre text
    pct = int(passed / total * 100) if total else 0
    centre = (
        f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" '
        f'fill="#e6edf3" font-size="26" font-weight="700" font-family="Courier New,monospace">{pct}%</text>'
        f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
        f'fill="#8b949e" font-size="11" font-family="sans-serif">pass rate</text>'
    )

    svg = (
        f'<svg width="180" height="180" viewBox="0 0 180 180" xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#21262d" stroke-width="{sw}"/>'
        + "".join(segments)
        + centre
        + "</svg>"
    )
    return svg


def make_tc_card(tc):
    name = tc.get("name", "Unknown")
    status = tc.get("status", "UNKNOWN").upper()
    description = tc.get("description", "")
    steps = tc.get("steps", [])

    step_html = ""
    for step in steps:
        sname = step.get("name", "")
        sstatus = step.get("status", "").upper()
        icon = STEP_ICONS.get(sstatus, "·")
        step_html += (
            f'<div class="step {sstatus}">'
            f'<span class="step-icon">{icon}</span>'
            f"<span>{sname}</span>"
            f'<span style="margin-left:auto;color:var(--muted)">{sstatus}</span>'
            f"</div>"
        )

    steps_section = f'<div class="steps">{step_html}</div>' if step_html else ""
    desc_section = f'<div class="tc-desc">{description}</div>' if description else ""

    body_content = desc_section + steps_section
    body_html = (
        f'<div class="tc-body">{body_content}</div>'
        if body_content.strip()
        else ""
    )

    icon_char = STEP_ICONS.get(status, "?")

    return f"""
    <div class="tc-card" data-status="{status}">
      <div class="tc-header">
        <div class="tc-icon">{icon_char}</div>
        <div class="tc-name">{name}</div>
        <div class="tc-status-pill">{status}</div>
      </div>
      {body_html}
    </div>"""


def generate_dashboard(data: dict, output_path: str = "dashboard.html"):
    """
    Generate the dashboard HTML from a data dict and write to output_path.

    Expected data structure:
    {
      "run_time": "2026-05-15 05:08:47",
      "build_status": "COMPLETE",
      "device": "Hfcl-Switch (192.168.180.164)",
      "test_module": "Layer 2 - MAC Aging",
      "mac_aging_time": "50 seconds",
      "branch": "layer2",
      "jenkins_job": "Layer2-test-cases",
      "interface": "enp2s0",
      "test_cases": [
        {
          "name": "TC01_VerifyMacAgingConfigpyATS",
          "status": "PASSED",
          "description": "Verify MAC aging-time is correctly configured on switch",
          "steps": [
            {"name": "verify_aging_time", "status": "PASSED"}
          ]
        },
        ...
      ]
    }
    """
    tcs = data.get("test_cases", [])
    total = len(tcs)
    passed = sum(1 for t in tcs if t.get("status", "").upper() == "PASSED")
    failed = sum(1 for t in tcs if t.get("status", "").upper() == "FAILED")
    errored = sum(1 for t in tcs if t.get("status", "").upper() == "ERRORED")
    skipped = sum(1 for t in tcs if t.get("status", "").upper() == "SKIPPED")
    success_rate = int(passed / total * 100) if total else 0

    build_status = data.get("build_status", "COMPLETE")
    build_class = "fail" if build_status.upper() in ("FAILED", "FAIL", "ERROR") else ""

    donut_svg = make_donut_svg(passed, failed, errored, skipped, total)
    tc_cards = "".join(make_tc_card(t) for t in tcs)

    html = HTML_TEMPLATE.format(
        run_time=data.get("run_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        build_status=f"BUILD {build_status}",
        build_class=build_class,
        device=data.get("device", "—"),
        test_module=data.get("test_module", "—"),
        mac_aging_time=data.get("mac_aging_time", "—"),
        branch=data.get("branch", "—"),
        jenkins_job=data.get("jenkins_job", "—"),
        interface=data.get("interface", "—"),
        total=total,
        passed=passed,
        failed=failed,
        errored=errored,
        skipped=skipped,
        success_rate=success_rate,
        donut_svg=donut_svg,
        tc_cards=tc_cards,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Dashboard written → {output_path}")
    return html


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate NETAUTO test dashboard")
    parser.add_argument("--results", default=None, help="Path to results JSON file")
    parser.add_argument("--output", default="reports/dashboard.html", help="Output HTML path")
    args = parser.parse_args()

    if args.results:
        with open(args.results) as f:
            data = json.load(f)
    else:
        # ── Demo / sample data so you can run the script standalone ──────────
        data = {
            "run_time": "2026-05-15 05:08:47",
            "build_status": "COMPLETE",
            "device": "Hfcl-Switch (192.168.180.164)",
            "test_module": "Layer 2 - MAC Aging",
            "mac_aging_time": "50 seconds",
            "branch": "layer2",
            "jenkins_job": "Layer2-test-cases",
            "interface": "enp2s0",
            "test_cases": [
                {
                    "name": "TC01_VerifyMacAgingConfigpyATS",
                    "status": "PASSED",
                    "description": "Verify MAC aging-time is correctly configured on switch",
                    "steps": [
                        {"name": "verify_aging_time", "status": "PASSED"},
                    ],
                },
                {
                    "name": "TC02_VerifyMacLearningpyATS",
                    "status": "ERRORED",
                    "description": "Verify MAC entries are learned after bi-directional traffic",
                    "steps": [
                        {"name": "send_bidirectional_traffic", "status": "ERRORED"},
                        {"name": "verify_src_mac_learned", "status": "BLOCKED"},
                        {"name": "verify_dst_mac_learned", "status": "BLOCKED"},
                        {"name": "verify_entries_are_dynamic", "status": "BLOCKED"},
                    ],
                },
                {
                    "name": "TC03_VerifyMacFlushedAfterExpirypyATS",
                    "status": "FAILED",
                    "description": "Verify MAC entries are flushed after aging timer expires",
                    "steps": [
                        {"name": "wait_for_aging_timer", "status": "PASSED"},
                        {"name": "verify_mac_table_empty", "status": "FAILED"},
                    ],
                },
                {
                    "name": "TC04_VerifyMacRelearningpyATS",
                    "status": "SKIPPED",
                    "description": "Verify MAC re-learning after flush",
                    "steps": [],
                },
            ],
        }

    generate_dashboard(data, args.output)
