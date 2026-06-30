#!/usr/bin/env python3
"""
generate_dashboard.py
---------------------
Parses pyATS logs for MAC Aging and MAC Movement tests
and generates a combined HTML dashboard.
"""

import re
import json
import argparse
from datetime import datetime
from pathlib import Path

# ─── Argument parsing ────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--log",      required=True,  help="pyATS log for MAC Aging")
parser.add_argument("--log2",     default="",     help="pyATS log for MAC Movement")
parser.add_argument("--log3",     default="",     help="pyATS log for VLAN Access-Access")
parser.add_argument("--ansible",  default="",     help="Ansible log for MAC Aging")
parser.add_argument("--ansible2", default="",     help="Ansible log for MAC Movement")
parser.add_argument("--ansible3", default="",     help="Ansible log for VLAN Access-Access")
parser.add_argument("--result-json", default="",  help="Phase 3 structured summary (VLAN Access-Access)")
parser.add_argument("--output",   required=True,  help="Output HTML dashboard path")
parser.add_argument("--device",   default="Hfcl-Switch (192.168.180.146)")
parser.add_argument("--module",   default="Layer 2 - MAC Aging & MAC Movement")
parser.add_argument("--aging",    default="50 seconds")
args = parser.parse_args()

def read_file(path):
    p = Path(path)
    return p.read_text(errors="ignore") if path and p.exists() else ""

log_aging    = read_file(args.log)
log_movement = read_file(args.log2)
log_vlan_aa  = read_file(args.log3)
ansible_aging    = read_file(args.ansible)
ansible_movement = read_file(args.ansible2)
ansible_vlan_aa  = read_file(args.ansible3)

def read_json(path):
    p = Path(path)
    if path and p.exists():
        try:
            return json.loads(p.read_text(errors="ignore"))
        except (json.JSONDecodeError, OSError):
            return None
    return None

vlan_result = read_json(args.result_json)

TC_DESCRIPTIONS = {
    # MAC Aging
    "TC01_VerifyMacAgingConfig":        "Verify MAC aging-time is correctly configured on switch",
    "TC02_VerifyMacLearning":           "Verify MAC entries are learned after bi-directional traffic",
    "TC03_VerifyMacFlushedAfterExpiry": "Verify dynamic MACs are flushed after aging-time expires",
    "TC04_VerifyStaticMacsRemain":      "Verify static MAC entries remain after aging-time expires",
    # MAC Movement
    "TC01_VerifyMacLearnedOnPort1":     "Verify MAC learned on Port 1 (Gi 1/1) after traffic from Laptop 1",
    "TC02_VerifyMacMovesToPort2":       "Verify MAC moves to Port 2 (Gi 1/2) after traffic from Laptop 2",
    "TC03_VerifyOldPortEntryRemoved":   "Verify old port entry is removed after MAC movement",
    "TC04_VerifyDynamicAfterMovement":  "Verify MAC entry type is Dynamic after movement",
    # VLAN Access-Access
    "TC01_Verify_VLAN":                 "Verify VLAN exists on the switch",
    "TC02_Verify_Interface_Config":     "Verify access port mode, VLAN assignment, and admin status",
    "TC03_Verify_Link_Status":          "Verify both access interfaces are operationally up",
    "TC04_Verify_MAC_Table":            "Verify dynamic MAC learning on both access ports",
    "TC05_Verify_Interface_Counters":   "Verify interface traffic counters incremented",
    "TC06_Verify_Traffic":              "Verify sender/receiver packet counts, loss %, and MAC visibility",
}

def parse_pyats(log, source_label):
    testcases, current_tc = [], None
    tc_pat   = re.compile(r'\|-- (TC\w+)\s+(PASSED|FAILED|ERRORED|BLOCKED|SKIPPED|ABORTED)')
    step_pat = re.compile(r'\|   [|`]-- (\w+)\s+(PASSED|FAILED|ERRORED|BLOCKED|SKIPPED|ABORTED)')
    for line in log.splitlines():
        tc_m, step_m = tc_pat.search(line), step_pat.search(line)
        if tc_m:
            current_tc = {
                "name":        tc_m.group(1),
                "result":      tc_m.group(2),
                "description": TC_DESCRIPTIONS.get(tc_m.group(1), tc_m.group(1)),
                "steps":       [],
                "source":      source_label,
            }
            testcases.append(current_tc)
        elif step_m and current_tc:
            current_tc["steps"].append({"name": step_m.group(1), "result": step_m.group(2)})
    rate_m = re.search(r'Success Rate\s+([\d.]+)%', log)
    return testcases, (float(rate_m.group(1)) if rate_m else None)

def parse_ansible(log, source_label):
    testcases = []
    task_pat   = re.compile(r'TASK \[(.+?)\]')
    result_pat = re.compile(r'(ok|changed|fatal|failed|FAILED):\s*\[localhost\]')
    ignore_pat = re.compile(r'\.\.\.ignoring')
    lines, current_task, tc_index, i = log.splitlines(), None, 0, 0
    while i < len(lines):
        tm = task_pat.search(lines[i])
        if tm:
            current_task = tm.group(1).strip()
        else:
            rm = result_pat.search(lines[i])
            if rm and current_task:
                raw  = rm.group(1).lower()
                look = "\n".join(lines[i:i+10])
                if "fatal" in raw or "failed" in raw:
                    result = "SKIPPED" if ignore_pat.search(look) else "FAILED"
                else:
                    result = "PASSED"
                tc_index += 1
                testcases.append({
                    "name":        current_task,
                    "result":      result,
                    "description": "Ansible task result",
                    "steps":       [],
                    "source":      source_label,
                })
                current_task = None
        i += 1
    seen, unique = set(), []
    for tc in testcases:
        if tc["name"] not in seen:
            seen.add(tc["name"]); unique.append(tc)
    return unique

# Parse MAC Aging results
aging_tcs, aging_rate = parse_pyats(log_aging, "MAC Aging")
if not aging_tcs and ansible_aging:
    print("[INFO] MAC Aging: falling back to Ansible log.")
    aging_tcs = parse_ansible(ansible_aging, "MAC Aging")

# Parse MAC Movement results
movement_tcs, movement_rate = parse_pyats(log_movement, "MAC Movement")
if not movement_tcs and ansible_movement:
    print("[INFO] MAC Movement: falling back to Ansible log.")
    movement_tcs = parse_ansible(ansible_movement, "MAC Movement")

# Parse VLAN Access-Access results
vlan_aa_tcs, vlan_aa_rate = parse_pyats(log_vlan_aa, "VLAN Access-Access")
if not vlan_aa_tcs and ansible_vlan_aa:
    print("[INFO] VLAN Access-Access: falling back to Ansible log.")
    vlan_aa_tcs = parse_ansible(ansible_vlan_aa, "VLAN Access-Access")

# Combined
all_tcs = aging_tcs + movement_tcs + vlan_aa_tcs
total   = len(all_tcs)

counts = {"PASSED":0,"FAILED":0,"ERRORED":0,"BLOCKED":0,"SKIPPED":0}
for tc in all_tcs:
    if tc["result"] in counts: counts[tc["result"]] += 1

passed  = counts["PASSED"]
failed  = counts["FAILED"]
errored = counts["ERRORED"]
skipped = counts["BLOCKED"] + counts["SKIPPED"]
success_rate = round(100 * passed / total, 1) if total else 0.0

SC = {"PASSED":"#00ff9d","FAILED":"#ff3b5c","ERRORED":"#ffd600","BLOCKED":"#4a6080","SKIPPED":"#4a6080"}
SI = {"PASSED":"✓","FAILED":"✗","ERRORED":"⚠","BLOCKED":"◌","SKIPPED":"—"}

# Per-module badge colors. Falls back to a stable hash-based color
# for any future module instead of mislabeling it.
MODULE_COLORS = {
    "MAC Aging": "#00d4ff",
    "MAC Movement": "#ff9d00",
    "VLAN Access-Access": "#b18cff",
}

def make_donut(p, f, e, s, tot):
    if tot == 0:
        return ('<svg width="200" height="200" viewBox="0 0 200 200">'
                '<circle cx="100" cy="100" r="72" fill="none" stroke="#1a2d4a" stroke-width="28"/>'
                '<text x="100" y="107" text-anchor="middle" fill="#4a6080" font-size="14" '
                'font-family="Courier New,monospace">No data</text></svg>')
    colors = ["#00ff9d","#ff3b5c","#ffd600","#4a6080"]
    vals   = [p, f, e, s]
    cx, cy, r, sw = 100, 100, 72, 28
    circ   = 2 * 3.14159265 * r
    angle  = -90
    segs   = []
    for i, val in enumerate(vals):
        if val == 0: continue
        frac = val / tot
        dash = frac * circ
        gap  = circ - dash
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colors[i]}" '
            f'stroke-width="{sw}" stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{circ/4:.2f}" transform="rotate({angle} {cx} {cy})"/>'
        )
        angle += frac * 360
    pct = int(p / tot * 100)
    return (
        f'<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#0b1120" stroke-width="{sw}"/>'
        + "".join(segs)
        + f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#e6edf3" font-size="30" '
          f'font-weight="700" font-family="Courier New,monospace">{pct}%</text>'
        + f'<text x="{cx}" y="{cy+16}" text-anchor="middle" fill="#4a6080" font-size="12" '
          f'font-family="Courier New,monospace">pass rate</text></svg>'
    )

def tc_cards(tcs):
    rows = []
    for idx, tc in enumerate(tcs):
        st  = tc["result"].upper()
        col = SC.get(st, "#4a6080")
        ico = SI.get(st, "?")

        # Source badge color
        badge_col = MODULE_COLORS.get(tc.get("source"), "#4a6080")
        src = (
            f'<span style="font-size:0.6rem;background:rgba(0,212,255,0.1);border:1px solid '
            f'rgba(0,212,255,0.25);padding:2px 7px;border-radius:3px;color:{badge_col};margin-left:8px">'
            f'{tc.get("source","")}</span>'
        ) if tc.get("source") else ""

        shtml = ""
        for s in tc["steps"]:
            sc2 = SC.get(s["result"].upper(), "#4a6080")
            si2 = SI.get(s["result"].upper(), "·")
            shtml += (
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
                f'border-bottom:1px solid rgba(26,45,74,0.5);font-size:0.78rem">'
                f'<span style="color:{sc2};width:16px;text-align:center">{si2}</span>'
                f'<span style="font-family:Courier New,monospace;color:#c8d8e8;flex:1">{s["name"]}</span>'
                f'<span style="font-family:Courier New,monospace;font-size:0.68rem;color:{sc2}">{s["result"]}</span>'
                f'</div>'
            )
        if not shtml:
            shtml = '<div style="color:#4a6080;font-size:0.75rem;font-family:Courier New,monospace">No sub-steps recorded</div>'

        rows.append(
            f'<div class="tc-card" data-status="{st}" style="border-left:4px solid {col}">'
            f'<div class="tc-header" onclick="toggle({idx})">'
            f'<span style="color:{col};font-size:1rem;width:20px;text-align:center">{ico}</span>'
            f'<span class="tc-name">{tc["name"]}{src}</span>'
            f'<span class="tc-badge" style="color:{col};border-color:{col}40;background:{col}15">{st}</span>'
            f'<span class="chevron" id="chev-{idx}">▶</span></div>'
            f'<div class="tc-steps" id="steps-{idx}" style="display:none">'
            f'<div style="font-family:Courier New,monospace;font-size:0.72rem;color:#4a6080;margin-bottom:10px">{tc["description"]}</div>'
            f'{shtml}</div></div>'
        )
    return "\n".join(rows)

# Module summary cards
def module_summary(tcs, label):
    mc = {"PASSED":0,"FAILED":0,"ERRORED":0,"BLOCKED":0,"SKIPPED":0}
    for tc in tcs:
        if tc["result"] in mc: mc[tc["result"]] += 1
    tot  = len(tcs)
    rate = round(100 * mc["PASSED"] / tot, 1) if tot else 0.0
    col  = "#00ff9d" if rate == 100 else "#ffd600" if rate >= 50 else "#ff3b5c"
    return (
        f'<div class="module-card">'
        f'<div class="module-title">{label}</div>'
        f'<div class="module-stats">'
        f'<span style="color:#00ff9d">✓ {mc["PASSED"]} Passed</span>'
        f'<span style="color:#ff3b5c">✗ {mc["FAILED"]} Failed</span>'
        f'<span style="color:#ffd600">⚠ {mc["ERRORED"]} Errored</span>'
        f'<span style="color:#4a6080">◌ {mc["BLOCKED"]+mc["SKIPPED"]} Skipped</span>'
        f'</div>'
        f'<div style="background:rgba(255,255,255,0.05);border-radius:4px;height:8px;margin-top:10px;overflow:hidden">'
        f'<div style="width:{rate}%;height:100%;background:{col};border-radius:4px"></div>'
        f'</div>'
        f'<div style="font-family:Courier New,monospace;font-size:0.8rem;color:{col};margin-top:6px">{rate}% success</div>'
        f'</div>'
    )

now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
donut   = make_donut(passed, failed, errored, skipped, total)
tc_html = tc_cards(all_tcs)

# Phase 3: Traffic Metrics table, built from the structured summary
# TC06 writes (vlan_access_access_result.json), not from log scraping.
def traffic_metrics_table(result):
    if not result:
        return (
            '<div style="font-family:Courier New,monospace;font-size:0.75rem;'
            'color:#4a6080;padding:16px 0">No traffic metrics available '
            '(--result-json not provided or file missing).</div>'
        )

    status = result.get("status", "UNKNOWN")
    col    = SC.get(status, "#4a6080")

    cols = [
        ("Test Name",        result.get("test_name", "-")),
        ("VLAN",             result.get("vlan", "-")),
        ("Ports",            result.get("ports", "-")),
        ("Packets Sent",     result.get("packets_sent", "-")),
        ("Packets Received", result.get("packets_received", "-")),
        ("Packet Loss %",    f'{result.get("packet_loss_percent", "-")}%'),
        ("MAC Learned",      "Yes" if result.get("mac_learned") else "No"),
        ("Execution Time",   f'{result.get("execution_time_seconds", "-")}s'),
        ("Result",           status),
    ]

    cells = ""
    for label, val in cols:
        val_col = col if label == "Result" else "#c8d8e8"
        cells += (
            f'<div style="flex:1;min-width:110px;padding:12px 10px">'
            f'<div style="font-family:Courier New,monospace;font-size:0.6rem;'
            f'letter-spacing:1px;text-transform:uppercase;color:#4a6080;margin-bottom:5px">{label}</div>'
            f'<div style="font-family:Courier New,monospace;font-size:0.85rem;'
            f'color:{val_col};font-weight:700">{val}</div>'
            f'</div>'
        )

    errors_html = ""
    errs = result.get("errors") or []
    if errs:
        items = "".join(f'<li style="margin-bottom:4px">{e}</li>' for e in errs)
        errors_html = (
            f'<div style="margin-top:10px;padding:10px 14px;background:rgba(255,59,92,0.08);'
            f'border:1px solid rgba(255,59,92,0.3);border-radius:6px;font-family:Courier New,monospace;'
            f'font-size:0.72rem;color:#ff3b5c"><ul style="margin-left:18px">{items}</ul></div>'
        )

    return (
        f'<div style="background:var(--panel);border:1px solid var(--border);border-left:4px solid {col};'
        f'border-radius:8px;padding:6px 8px">'
        f'<div style="display:flex;flex-wrap:wrap">{cells}</div>'
        f'{errors_html}'
        f'</div>'
    )

traffic_metrics = traffic_metrics_table(vlan_result)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>HFCL Test Dashboard</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#060a10;--panel:#0b1120;--border:#1a2d4a;--accent:#00d4ff;--green:#00ff9d;--red:#ff3b5c;--yellow:#ffd600;--text:#c8d8e8;--dim:#4a6080}}
body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0}}
.shell{{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:32px 20px 60px}}
.hdr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:36px;padding-bottom:20px;border-bottom:1px solid var(--border)}}
.hdr-title{{font-size:1.9rem;font-weight:700;letter-spacing:3px;color:#fff;text-transform:uppercase}}
.hdr-title span{{color:var(--accent)}}
.hdr-sub{{font-family:Courier New,monospace;color:var(--dim);font-size:0.72rem;margin-top:4px;letter-spacing:2px}}
.live{{display:flex;align-items:center;gap:8px;background:rgba(0,255,157,0.08);border:1px solid rgba(0,255,157,0.3);padding:8px 16px;border-radius:4px;font-family:Courier New,monospace;font-size:0.72rem;color:var(--green);letter-spacing:2px}}
.dot{{width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 1.5s infinite}}
@keyframes pulse{{0%,100%{{opacity:1;box-shadow:0 0 6px var(--green)}}50%{{opacity:.4;box-shadow:none}}}}
.sec{{font-size:0.85rem;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--accent);margin-bottom:14px;display:flex;align-items:center;gap:10px}}
.sec::after{{content:'';flex:1;height:1px;background:var(--border)}}
.meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:28px}}
.meta-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px 18px}}
.meta-key{{font-family:Courier New,monospace;font-size:0.62rem;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:5px}}
.meta-val{{font-family:Courier New,monospace;font-size:0.82rem;color:var(--accent)}}
.module-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:28px}}
.module-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:18px 20px}}
.module-title{{font-family:Courier New,monospace;font-size:0.85rem;color:#fff;font-weight:700;margin-bottom:12px;letter-spacing:1px}}
.module-stats{{display:flex;gap:16px;flex-wrap:wrap;font-family:Courier New,monospace;font-size:0.75rem}}
.sum-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px}}
.sum-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:20px 14px;text-align:center;position:relative;overflow:hidden}}
.sum-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.c-tot::before{{background:var(--accent)}}.c-pass::before{{background:var(--green)}}.c-fail::before{{background:var(--red)}}.c-err::before{{background:var(--yellow)}}.c-skip::before{{background:var(--dim)}}
.sum-num{{font-size:2.8rem;font-weight:700;line-height:1;margin-bottom:5px}}
.c-tot .sum-num{{color:var(--accent)}}.c-pass .sum-num{{color:var(--green)}}.c-fail .sum-num{{color:var(--red)}}.c-err .sum-num{{color:var(--yellow)}}.c-skip .sum-num{{color:var(--dim)}}
.sum-lbl{{font-family:Courier New,monospace;font-size:0.62rem;letter-spacing:2px;text-transform:uppercase;color:var(--dim)}}
.mid{{display:grid;grid-template-columns:1fr 240px;gap:20px;margin-bottom:28px;align-items:center}}
.rate-panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:24px}}
.rate-lbl{{font-family:Courier New,monospace;font-size:0.7rem;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin-bottom:12px}}
.rate-track{{background:rgba(255,255,255,0.05);border-radius:4px;height:14px;overflow:hidden;margin-bottom:12px}}
.rate-fill{{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--green),var(--accent));box-shadow:0 0 12px rgba(0,255,157,.4);width:0;transition:width 1s ease}}
.rate-pct{{font-size:2.4rem;font-weight:700;color:var(--green);font-family:Courier New,monospace}}
.donut-panel{{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:20px;display:flex;flex-direction:column;align-items:center;gap:12px}}
.donut-legend{{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;width:100%}}
.leg{{display:flex;align-items:center;gap:6px;font-family:Courier New,monospace;font-size:0.65rem;color:var(--dim)}}
.leg-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.filter-bar{{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}}
.fbtn{{font-family:Courier New,monospace;font-size:0.68rem;padding:5px 14px;border-radius:4px;border:1px solid var(--border);background:var(--panel);color:var(--dim);cursor:pointer;letter-spacing:1px}}
.fbtn:hover,.fbtn.active{{border-color:var(--accent);color:var(--accent);background:rgba(0,212,255,.08)}}
.tc-card{{background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:10px;transition:border-color .2s}}
.tc-card:hover{{border-color:rgba(0,212,255,.4)}}
.tc-header{{display:flex;align-items:center;gap:14px;padding:14px 18px;cursor:pointer}}
.tc-name{{font-family:Courier New,monospace;font-size:0.8rem;color:#fff;flex:1}}
.tc-badge{{font-family:Courier New,monospace;font-size:0.68rem;padding:3px 10px;border-radius:4px;border:1px solid;letter-spacing:1px}}
.tc-steps{{padding:12px 18px 14px;border-top:1px solid var(--border)}}
.chevron{{color:var(--dim);font-size:0.65rem;transition:transform .2s;flex-shrink:0}}
.chevron.open{{transform:rotate(90deg)}}
</style>
</head>
<body>
<div class="shell">
  <div class="hdr">
    <div>
      <div class="hdr-title">HFCL<span> TEST</span> DASHBOARD</div>
      <div class="hdr-sub">RUN: {now.upper()} &nbsp;·&nbsp; BRANCH: LAYER2 &nbsp;·&nbsp; JOB: LAYER2-TEST-CASES</div>
    </div>
    <div class="live"><div class="dot"></div>BUILD COMPLETE</div>
  </div>

  <div class="sec">Pipeline Info</div>
  <div class="meta-grid">
    <div class="meta-card"><div class="meta-key">Device</div><div class="meta-val">{args.device}</div></div>
    <div class="meta-card"><div class="meta-key">Test Modules</div><div class="meta-val">{args.module}</div></div>
    <div class="meta-card"><div class="meta-key">MAC Aging Time</div><div class="meta-val">{args.aging}</div></div>
    <div class="meta-card"><div class="meta-key">Branch</div><div class="meta-val">layer2</div></div>
    <div class="meta-card"><div class="meta-key">Jenkins Job</div><div class="meta-val">Layer2-test-cases</div></div>
    <div class="meta-card"><div class="meta-key">Laptop 1 / Laptop 2</div><div class="meta-val">192.168.180.142 / 192.168.180.155</div></div>
  </div>

  <div class="sec">Module Summary</div>
  <div class="module-grid">
    {module_summary(aging_tcs, "🔁 MAC Aging")}
    {module_summary(movement_tcs, "↔️  MAC Movement")}
    {module_summary(vlan_aa_tcs, "🔌 VLAN Access-Access")}
  </div>

  <div class="sec">VLAN Access-Access Traffic Metrics</div>
  {traffic_metrics}

  <div class="sec">Overall Summary</div>
  <div class="sum-grid">
    <div class="sum-card c-tot"><div class="sum-num">{total}</div><div class="sum-lbl">Total</div></div>
    <div class="sum-card c-pass"><div class="sum-num">{passed}</div><div class="sum-lbl">Passed</div></div>
    <div class="sum-card c-fail"><div class="sum-num">{failed}</div><div class="sum-lbl">Failed</div></div>
    <div class="sum-card c-err"><div class="sum-num">{errored}</div><div class="sum-lbl">Errored</div></div>
    <div class="sum-card c-skip"><div class="sum-num">{skipped}</div><div class="sum-lbl">Skipped</div></div>
  </div>

  <div class="mid">
    <div class="rate-panel">
      <div class="rate-lbl">Overall Success Rate</div>
      <div class="rate-track"><div class="rate-fill" id="rf"></div></div>
      <div class="rate-pct" id="rp">0%</div>
    </div>
    <div class="donut-panel">
      {donut}
      <div class="donut-legend">
        <div class="leg"><div class="leg-dot" style="background:var(--green)"></div>Passed ({passed})</div>
        <div class="leg"><div class="leg-dot" style="background:var(--red)"></div>Failed ({failed})</div>
        <div class="leg"><div class="leg-dot" style="background:var(--yellow)"></div>Errored ({errored})</div>
        <div class="leg"><div class="leg-dot" style="background:var(--dim)"></div>Skipped ({skipped})</div>
      </div>
    </div>
  </div>

  <div class="sec">Test Cases</div>
  <div class="filter-bar">
    <button class="fbtn active" onclick="filt('ALL',this)">ALL</button>
    <button class="fbtn" onclick="filt('PASSED',this)">PASSED</button>
    <button class="fbtn" onclick="filt('FAILED',this)">FAILED</button>
    <button class="fbtn" onclick="filt('ERRORED',this)">ERRORED</button>
    <button class="fbtn" onclick="filtModule('MAC Aging',this)">MAC AGING</button>
    <button class="fbtn" onclick="filtModule('MAC Movement',this)">MAC MOVEMENT</button>
    <button class="fbtn" onclick="filtModule('VLAN Access-Access',this)">VLAN ACCESS-ACCESS</button>
  </div>
  <div id="tc-grid">{tc_html}</div>

  <div style="margin-top:40px;border-top:1px solid var(--border);padding-top:14px;text-align:center;font-family:Courier New,monospace;font-size:0.65rem;color:var(--dim)">
    HFCL TEST DASHBOARD &nbsp;·&nbsp; Generated {now}
  </div>
</div>
<script>
  setTimeout(function(){{
    document.getElementById('rf').style.width='{success_rate}%';
    document.getElementById('rp').textContent='{success_rate}%';
  }},400);
  function toggle(i){{
    var s=document.getElementById('steps-'+i);
    var c=document.getElementById('chev-'+i);
    var open=s.style.display==='none';
    s.style.display=open?'':'none';
    c.classList.toggle('open',open);
  }}
  function filt(status,btn){{
    document.querySelectorAll('.fbtn').forEach(function(b){{b.classList.remove('active')}});
    btn.classList.add('active');
    document.querySelectorAll('.tc-card').forEach(function(c){{
      c.style.display=(status==='ALL'||c.dataset.status===status)?'':'none';
    }});
  }}
  function filtModule(mod,btn){{
    document.querySelectorAll('.fbtn').forEach(function(b){{b.classList.remove('active')}});
    btn.classList.add('active');
    document.querySelectorAll('.tc-card').forEach(function(c){{
      var badge=c.querySelector('.tc-name span');
      var show=badge&&badge.textContent.trim()===mod;
      c.style.display=show?'':'none';
    }});
  }}
</script>
</body>
</html>"""

Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(HTML, encoding="utf-8")
print(f"Dashboard generated: {args.output}")
print(f"Total:{total} Passed:{passed} Failed:{failed} Errored:{errored} Skipped:{skipped} Rate:{success_rate}%")
