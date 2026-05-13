#!/usr/bin/env python3
"""
generate_dashboard.py
---------------------
Parses pyATS test log (and falls back to Ansible log) to generate
an HTML dashboard showing pass/fail results.

Usage:
    python3 scripts/generate_dashboard.py \
        --log     reports/pyats_run.log \
        --ansible reports/ansible_run.log \
        --output  reports/dashboard.html \
        --device  "Hfcl-Switch (192.168.180.96)" \
        --module  "Layer 2 - MAC Aging" \
        --aging   "50 seconds"
"""

import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# ─── Argument parsing ────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--log",     required=True,  help="Path to pyATS run log")
parser.add_argument("--ansible", default="",     help="Path to Ansible run log (fallback source)")
parser.add_argument("--output",  required=True,  help="Output HTML dashboard path")
parser.add_argument("--device",  default="Hfcl-Switch (192.168.180.96)")
parser.add_argument("--module",  default="Layer 2 — MAC Aging")
parser.add_argument("--aging",   default="50 seconds")
args = parser.parse_args()

log_text     = Path(args.log).read_text(errors="ignore") if Path(args.log).exists() else ""
ansible_text = Path(args.ansible).read_text(errors="ignore") if args.ansible and Path(args.ansible).exists() else ""

# ─── Descriptions map ────────────────────────────────────────────────────────
TC_DESCRIPTIONS = {
    "TC01_VerifyMacAgingConfig":        "Verify MAC aging-time is correctly configured on switch",
    "TC02_VerifyMacLearning":           "Verify MAC entries are learned after bi-directional traffic",
    "TC03_VerifyMacFlushedAfterExpiry": "Verify dynamic MACs are flushed after aging-time expires",
    "TC04_VerifyStaticMacsRemain":      "Verify static MAC entries remain after aging-time expires",
}

# ─── Parse pyATS log ─────────────────────────────────────────────────────────
def parse_pyats(log):
    testcases = []
    current_tc = None
    tc_pat   = re.compile(r'\|-- (TC\w+)\s+(PASSED|FAILED|ERRORED|BLOCKED|SKIPPED|ABORTED)')
    step_pat = re.compile(r'\|   [|`]-- (\w+)\s+(PASSED|FAILED|ERRORED|BLOCKED|SKIPPED|ABORTED)')

    for line in log.splitlines():
        tc_m   = tc_pat.search(line)
        step_m = step_pat.search(line)
        if tc_m:
            current_tc = {
                "id":          tc_m.group(1)[:4],
                "name":        tc_m.group(1),
                "result":      tc_m.group(2),
                "description": TC_DESCRIPTIONS.get(tc_m.group(1), tc_m.group(1)),
                "steps":       [],
                "source":      "pyATS",
            }
            testcases.append(current_tc)
        elif step_m and current_tc:
            current_tc["steps"].append({"name": step_m.group(1), "result": step_m.group(2)})

    rate_m = re.search(r'Success Rate\s+([\d.]+)%', log)
    rate   = float(rate_m.group(1)) if rate_m else None
    return testcases, rate

# ─── Parse Ansible log as fallback ───────────────────────────────────────────
def parse_ansible(log):
    """
    Convert Ansible TASK results into pseudo test-cases so the dashboard
    is never empty even when pyATS cannot run.
    """
    testcases = []
    # Match lines like:  TASK [STEP 1 | Configure MAC aging-time to 50 seconds] ***
    task_pat   = re.compile(r'TASK \[(.+?)\]')
    # Result lines that follow:  ok/changed/failed/fatal
    result_pat = re.compile(r'(ok|changed|fatal|failed|FAILED):\s*\[localhost\]')
    # Assert pass marker
    assert_pat = re.compile(r'"msg":\s*"(✅[^"]+)"')
    # Ignore-style warning
    ignore_pat = re.compile(r'\.\.\.ignoring')

    lines       = log.splitlines()
    current_task = None
    tc_index     = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        tm = task_pat.search(line)
        if tm:
            current_task = tm.group(1).strip()
        else:
            rm = result_pat.search(line)
            if rm and current_task:
                raw = rm.group(1).lower()
                # Look ahead a few lines for assert msg or ignore
                lookahead = "\n".join(lines[i:i+10])
                if "fatal" in raw or "failed" in raw:
                    if ignore_pat.search(lookahead):
                        result = "SKIPPED"   # ignored failure = warn only
                    else:
                        result = "FAILED"
                else:
                    if assert_pat.search(lookahead):
                        result = "PASSED"
                    else:
                        result = "PASSED" if raw in ("ok", "changed") else "ERRORED"

                tc_index += 1
                testcases.append({
                    "id":          f"A{tc_index:02d}",
                    "name":        current_task,
                    "result":      result,
                    "description": "Ansible task result",
                    "steps":       [],
                    "source":      "Ansible",
                })
                current_task = None
        i += 1

    # Dedupe by name (ansible log echoes tasks twice)
    seen, unique = set(), []
    for tc in testcases:
        if tc["name"] not in seen:
            seen.add(tc["name"])
            unique.append(tc)
    return unique

# ─── Decide which source to use ──────────────────────────────────────────────
testcases, success_rate = parse_pyats(log_text)

pyats_error = ""
if not testcases:
    # Detect the specific pyATS schema error so we can surface it
    if "SchemaUnsupportedKeyError" in log_text and "prompts" in log_text:
        pyats_error = (
            "pyATS testbed schema error: unsupported key 'generic' under "
            "connections.cli.prompts. Remove or rename that key in testbed.yaml."
        )
    elif log_text.strip():
        pyats_error = "pyATS produced no parseable test results (check pyats_run.log)."

    if ansible_text:
        print("[INFO] Falling back to Ansible log for test results.")
        testcases = parse_ansible(ansible_text)

    # Calculate rate from whatever we now have
    if testcases:
        passed       = sum(1 for t in testcases if t["result"] == "PASSED")
        success_rate = round(100 * passed / len(testcases), 1)
    else:
        success_rate = 0.0

if success_rate is None:
    passed       = sum(1 for t in testcases if t["result"] == "PASSED")
    success_rate = round(100 * passed / len(testcases), 1) if testcases else 0.0

counts = {"PASSED": 0, "FAILED": 0, "ERRORED": 0, "BLOCKED": 0, "SKIPPED": 0}
for tc in testcases:
    r = tc["result"]
    if r in counts:
        counts[r] += 1

run_data = {
    "timestamp":   datetime.now().isoformat(),
    "device":      args.device,
    "module":      args.module,
    "agingTime":   args.aging,
    "successRate": success_rate,
    "testcases":   testcases,
}

# ─── Build TC rows HTML ───────────────────────────────────────────────────────
def tc_rows_html(tcs):
    rows = []
    for tc in tcs:
        source_badge = (
            '<span style="font-size:0.6rem;background:rgba(0,212,255,0.1);'
            'border:1px solid rgba(0,212,255,0.25);padding:2px 7px;border-radius:3px;'
            f'color:#00d4ff;margin-left:8px;">{tc["source"]}</span>'
            if tc.get("source") else ""
        )
        steps_html = "".join([
            f'<div class="step-row">'
            f'<div class="step-dot" style="background:{"#00ff9d" if s["result"]=="PASSED" else "#ff3b5c" if s["result"]=="FAILED" else "#ffd600" if s["result"]=="ERRORED" else "#4a6080"}"></div>'
            f'<div class="step-name">{s["name"]}</div>'
            f'<div class="step-result step-{s["result"]}">{s["result"]}</div>'
            f'</div>'
            for s in tc["steps"]
        ]) if tc["steps"] else '<div style="color:#4a6080;font-size:0.75rem;font-family:\'Share Tech Mono\',monospace;">No sub-steps recorded</div>'

        rows.append(f"""
    <div class="tc-card">
      <div class="tc-header" onclick="toggleSteps(this)">
        <div class="tc-status status-{tc['result']}"></div>
        <div class="tc-name">{tc['name']}{source_badge}</div>
        <div class="tc-badge badge-{tc['result']}">{tc['result']}</div>
        <div class="chevron">▶</div>
      </div>
      <div class="tc-steps">
        <div style="font-family:'Share Tech Mono',monospace;font-size:0.72rem;color:var(--dim);margin-bottom:10px;">{tc['description']}</div>
        {steps_html}
      </div>
    </div>""")
    return "\n".join(rows)

error_banner = ""
if pyats_error:
    error_banner = f"""
  <div style="background:rgba(255,59,92,0.08);border:1px solid rgba(255,59,92,0.35);
              border-radius:8px;padding:14px 20px;margin-bottom:24px;
              font-family:'Share Tech Mono',monospace;font-size:0.78rem;color:#ff3b5c;">
    ⚠ {pyats_error}
  </div>"""

# ─── HTML template ────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Test Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&family=Exo+2:wght@300;400;700&display=swap');
  :root {{
    --bg:#060a10;--panel:#0b1120;--border:#1a2d4a;--accent:#00d4ff;
    --green:#00ff9d;--red:#ff3b5c;--yellow:#ffd600;--text:#c8d8e8;--dim:#4a6080;
  }}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--text);font-family:'Exo 2',sans-serif;min-height:100vh;overflow-x:hidden;}}
  body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}}
  .container{{position:relative;z-index:1;max-width:1200px;margin:0 auto;padding:30px 20px;}}
  .header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:40px;padding-bottom:20px;border-bottom:1px solid var(--border);}}
  .header-left h1{{font-family:'Rajdhani',sans-serif;font-size:2.2rem;font-weight:700;color:#fff;letter-spacing:3px;text-transform:uppercase;}}
  .header-left h1 span{{color:var(--accent);}}
  .header-left p{{font-family:'Share Tech Mono',monospace;color:var(--dim);font-size:0.75rem;margin-top:4px;letter-spacing:2px;}}
  .live-badge{{display:flex;align-items:center;gap:8px;background:rgba(0,255,157,0.08);border:1px solid rgba(0,255,157,0.3);padding:8px 16px;border-radius:4px;font-family:'Share Tech Mono',monospace;font-size:0.75rem;color:var(--green);letter-spacing:2px;}}
  .live-dot{{width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 1.5s infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1;box-shadow:0 0 6px var(--green);}}50%{{opacity:0.4;box-shadow:none;}}}}
  .summary-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:32px;}}
  .summary-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:20px 16px;text-align:center;position:relative;overflow:hidden;}}
  .summary-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;}}
  .card-passed::before{{background:var(--green);}} .card-failed::before{{background:var(--red);}}
  .card-errored::before{{background:var(--yellow);}} .card-blocked::before{{background:var(--dim);}}
  .card-total::before{{background:var(--accent);}}
  .card-number{{font-family:'Rajdhani',sans-serif;font-size:3rem;font-weight:700;line-height:1;margin-bottom:6px;}}
  .card-passed .card-number{{color:var(--green);text-shadow:0 0 20px rgba(0,255,157,0.5);}}
  .card-failed .card-number{{color:var(--red);text-shadow:0 0 20px rgba(255,59,92,0.5);}}
  .card-errored .card-number{{color:var(--yellow);text-shadow:0 0 20px rgba(255,214,0,0.5);}}
  .card-blocked .card-number{{color:var(--dim);}} .card-total .card-number{{color:var(--accent);text-shadow:0 0 20px rgba(0,212,255,0.5);}}
  .card-label{{font-family:'Share Tech Mono',monospace;font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:var(--dim);}}
  .rate-section{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:24px;margin-bottom:32px;display:flex;align-items:center;gap:32px;}}
  .rate-label{{font-family:'Rajdhani',sans-serif;font-size:1rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--dim);white-space:nowrap;min-width:140px;}}
  .rate-bar-wrap{{flex:1;}}
  .rate-bar-bg{{background:rgba(255,255,255,0.05);border-radius:4px;height:12px;overflow:hidden;margin-bottom:8px;}}
  .rate-bar-fill{{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--green),var(--accent));box-shadow:0 0 12px rgba(0,255,157,0.4);transition:width 1s ease;}}
  .rate-pct{{font-family:'Rajdhani',sans-serif;font-size:2.2rem;font-weight:700;color:var(--green);text-shadow:0 0 20px rgba(0,255,157,0.4);white-space:nowrap;}}
  .section-title{{font-family:'Rajdhani',sans-serif;font-size:1rem;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:var(--accent);margin-bottom:16px;display:flex;align-items:center;gap:10px;}}
  .section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
  .tc-grid{{display:grid;gap:10px;margin-bottom:32px;}}
  .tc-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;transition:border-color 0.2s;}}
  .tc-card:hover{{border-color:var(--accent);}}
  .tc-header{{display:flex;align-items:center;gap:16px;padding:16px 20px;cursor:pointer;}}
  .tc-status{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
  .status-PASSED{{background:var(--green);box-shadow:0 0 8px var(--green);}}
  .status-FAILED{{background:var(--red);box-shadow:0 0 8px var(--red);}}
  .status-ERRORED{{background:var(--yellow);box-shadow:0 0 8px var(--yellow);}}
  .status-SKIPPED{{background:#888;box-shadow:0 0 4px #888;}}
  .status-BLOCKED{{background:var(--dim);}}
  .tc-name{{font-family:'Share Tech Mono',monospace;font-size:0.82rem;color:#fff;flex:1;}}
  .tc-badge{{font-family:'Share Tech Mono',monospace;font-size:0.7rem;padding:4px 10px;border-radius:4px;letter-spacing:1px;}}
  .badge-PASSED{{background:rgba(0,255,157,0.12);color:var(--green);border:1px solid rgba(0,255,157,0.3);}}
  .badge-FAILED{{background:rgba(255,59,92,0.12);color:var(--red);border:1px solid rgba(255,59,92,0.3);}}
  .badge-ERRORED{{background:rgba(255,214,0,0.12);color:var(--yellow);border:1px solid rgba(255,214,0,0.3);}}
  .badge-BLOCKED,.badge-SKIPPED{{background:rgba(74,96,128,0.2);color:var(--dim);border:1px solid var(--border);}}
  .tc-steps{{padding:0 20px 16px 46px;display:none;}}
  .tc-steps.open{{display:block;}}
  .step-row{{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(26,45,74,0.5);font-size:0.8rem;}}
  .step-row:last-child{{border-bottom:none;}}
  .step-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0;}}
  .step-name{{font-family:'Share Tech Mono',monospace;color:var(--text);flex:1;}}
  .step-result{{font-family:'Share Tech Mono',monospace;font-size:0.7rem;}}
  .step-PASSED{{color:var(--green);}} .step-FAILED{{color:var(--red);}}
  .step-ERRORED{{color:var(--yellow);}} .step-BLOCKED,.step-SKIPPED{{color:var(--dim);}}
  .meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px;}}
  .meta-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px 20px;}}
  .meta-key{{font-family:'Share Tech Mono',monospace;font-size:0.65rem;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:6px;}}
  .meta-val{{font-family:'Share Tech Mono',monospace;font-size:0.85rem;color:var(--accent);}}
  .chevron{{color:var(--dim);font-size:0.7rem;transition:transform 0.2s;}}
  .chevron.open{{transform:rotate(90deg);}}
  .filter-bar{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;}}
  .filter-btn{{font-family:'Share Tech Mono',monospace;font-size:0.7rem;padding:6px 14px;border-radius:4px;border:1px solid var(--border);background:var(--panel);color:var(--dim);cursor:pointer;letter-spacing:1px;transition:all 0.2s;}}
  .filter-btn:hover,.filter-btn.active{{border-color:var(--accent);color:var(--accent);background:rgba(0,212,255,0.08);}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-left">
      <h1>NET<span>AUTO</span> TEST DASHBOARD</h1>
      <p>RUN: {run_data['timestamp'].replace('T',' ').split('.')[0].upper()}</p>
    </div>
    <div class="live-badge"><div class="live-dot"></div>BUILD COMPLETE</div>
  </div>

  {error_banner}

  <div class="section-title">Pipeline Info</div>
  <div class="meta-grid">
    <div class="meta-card"><div class="meta-key">Device</div><div class="meta-val">{run_data['device']}</div></div>
    <div class="meta-card"><div class="meta-key">Test Module</div><div class="meta-val">{run_data['module']}</div></div>
    <div class="meta-card"><div class="meta-key">MAC Aging Time</div><div class="meta-val">{run_data['agingTime']}</div></div>
    <div class="meta-card"><div class="meta-key">Branch</div><div class="meta-val">layer2</div></div>
    <div class="meta-card"><div class="meta-key">Jenkins Job</div><div class="meta-val">Layer2-test-cases</div></div>
    <div class="meta-card"><div class="meta-key">Interface</div><div class="meta-val">enp2s0</div></div>
  </div>

  <div class="section-title">Test Summary</div>
  <div class="summary-grid">
    <div class="summary-card card-total"><div class="card-number">{len(testcases)}</div><div class="card-label">Total</div></div>
    <div class="summary-card card-passed"><div class="card-number">{counts['PASSED']}</div><div class="card-label">Passed</div></div>
    <div class="summary-card card-failed"><div class="card-number">{counts['FAILED']}</div><div class="card-label">Failed</div></div>
    <div class="summary-card card-errored"><div class="card-number">{counts['ERRORED']}</div><div class="card-label">Errored</div></div>
    <div class="summary-card card-blocked"><div class="card-number">{counts['BLOCKED'] + counts['SKIPPED']}</div><div class="card-label">Skipped</div></div>
  </div>

  <div class="rate-section">
    <div class="rate-label">Success Rate</div>
    <div class="rate-bar-wrap">
      <div class="rate-bar-bg"><div class="rate-bar-fill" id="rate-bar" style="width:0%"></div></div>
    </div>
    <div class="rate-pct" id="rate-pct">0%</div>
  </div>

  <div class="section-title">Test Cases</div>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filter('ALL',this)">ALL</button>
    <button class="filter-btn" onclick="filter('PASSED',this)">PASSED</button>
    <button class="filter-btn" onclick="filter('FAILED',this)">FAILED</button>
    <button class="filter-btn" onclick="filter('ERRORED',this)">ERRORED</button>
    <button class="filter-btn" onclick="filter('SKIPPED',this)">SKIPPED</button>
  </div>
  <div class="tc-grid" id="tc-grid">
    {tc_rows_html(testcases)}
  </div>
</div>
<script>
  setTimeout(() => {{
    document.getElementById("rate-bar").style.width = "{success_rate}%";
    document.getElementById("rate-pct").textContent = "{success_rate}%";
  }}, 400);

  function toggleSteps(h) {{
    const s = h.nextElementSibling;
    const c = h.querySelector(".chevron");
    const o = s.classList.toggle("open");
    c.classList.toggle("open", o);
  }}

  function filter(status, btn) {{
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tc-card").forEach(card => {{
      if (status === "ALL") {{ card.style.display = ""; return; }}
      const badge = card.querySelector(".tc-badge");
      card.style.display = badge && badge.textContent.trim() === status ? "" : "none";
    }});
  }}
</script>
</body>
</html>"""

Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(HTML)
print(f"✅ Dashboard generated: {args.output}")
print(f"   Total: {len(testcases)} | Passed: {counts['PASSED']} | Failed: {counts['FAILED']} | Errored: {counts['ERRORED']} | Skipped: {counts['BLOCKED']+counts['SKIPPED']}")
print(f"   Success Rate: {success_rate}%")
