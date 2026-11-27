"""
assess.py
This is the main program. It reads my risk register (CSV file),
uses risk_engine.py to calculate every risk, and creates:
  reports/risk_report.html  - the report (open in a browser or print to PDF)
  reports/risk_results.csv  - all the results (open in Excel)

How to run:
  python assess.py                         (uses data/sample_register.csv)
  python assess.py data/other_file.csv     (use a different CSV)
"""

import argparse
import csv
import html
import os
import sys
from datetime import datetime

import risk_engine as engine

NUMERIC_FIELDS = {
    "likelihood": int,
    "confidentiality": int,
    "integrity": int,
    "availability": int,
    "control_effectiveness": float,
    "asset_value": float,
    "exposure_factor": float,
    "aro": float,
}
TEXT_FIELDS = ["id", "asset", "threat", "vulnerability", "category",
               "existing_control", "owner"]
REQUIRED = TEXT_FIELDS + list(NUMERIC_FIELDS)

# ===== Report details (shown on the cover of the report) =====
REPORT_TITLE = "Cybersecurity Risk Assessment Report"
AUTHOR = "Disharathan Shanmugam"
PROGRAMME = "Bachelor's degree in Cybersecurity"
SCENARIO = "Case study: a fictional university"

LEVEL_ORDER = ["Very High", "High", "Moderate", "Low", "Very Low"]
LEVEL_COLOURS = {
    "Very High": "#b3261e",
    "High": "#e8710a",
    "Moderate": "#f2c94c",
    "Low": "#8bc34a",
    "Very Low": "#3c9d5d",
}


# ===== Reading the CSV =====

def load_register(path):
    # read the CSV, check every row, and stop with a clear error if something is wrong
    if not os.path.exists(path):
        sys.exit(f"Error: file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"Error: CSV is missing column(s): {', '.join(missing)}")

        rows, errors = [], []
        for line_no, raw in enumerate(reader, start=2):  # start at 2 because line 1 is the column names
            row = {k: (raw[k] or "").strip() for k in TEXT_FIELDS}
            try:
                for field, cast in NUMERIC_FIELDS.items():
                    row[field] = cast(raw[field])
                rows.append(engine.assess(row))
            except (ValueError, TypeError) as e:
                errors.append(f"  line {line_no} ({raw.get('id', '?')}): {e}")

    if errors:
        sys.exit("Error: some rows are invalid:\n" + "\n".join(errors))
    if not rows:
        sys.exit("Error: the register has no risks in it.")
    return rows


# ===== Creating the outputs =====

def rank_key(r):
    # sort by NIST level first, then by score, then by money
    # (so a "Low" risk can never appear above a "Moderate" one)
    level_rank = len(LEVEL_ORDER) - LEVEL_ORDER.index(r["residual_level"])
    return (level_rank, r["residual_score"], r["ale_after"])


def rm(value):
    # 240000 -> "RM 240,000"
    return f"RM {value:,.0f}"


def print_summary(results):
    # print a short summary table in the terminal
    ranked = sorted(results, key=rank_key, reverse=True)
    print("\nCYBERSECURITY RISK ASSESSMENT - SUMMARY")
    print("=" * 78)
    print(f"{'ID':<5}{'Asset':<30}{'Inherent':<14}{'Residual':<14}{'ALE (after)':>15}")
    print("-" * 78)
    for r in ranked:
        print(f"{r['id']:<5}{r['asset'][:28]:<30}"
              f"{str(r['inherent_score']) + ' ' + r['inherent_level']:<14}"
              f"{str(r['residual_score']) + ' ' + r['residual_level']:<14}"
              f"{rm(r['ale_after']):>15}")
    print("-" * 78)
    total_before = sum(r["ale_before"] for r in results)
    total_after = sum(r["ale_after"] for r in results)
    print(f"Total ALE before controls: {rm(total_before)}")
    print(f"Total ALE after controls : {rm(total_after)}")


def write_csv(results, path):
    # save every calculated value to a CSV so it can be opened in Excel
    columns = REQUIRED + ["impact", "inherent_score", "inherent_level",
                          "residual_likelihood", "residual_score", "residual_level",
                          "sle", "ale_before", "ale_after", "meaning", "treatment"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            out = dict(r)
            for k in ("sle", "ale_before", "ale_after"):
                out[k] = round(out[k], 2)
            writer.writerow(out)


def heatmap_html(results, likelihood_key, caption):
    # build the 5x5 heat map: likelihood going up, impact going across
    # each box is coloured using the NIST table and shows the risk IDs inside it
    cells = {}
    for r in results:
        cells.setdefault((r[likelihood_key], r["impact"]), []).append(r["id"])

    rows = []
    for L in range(5, 0, -1):
        tds = [f'<th class="axis">{engine.LIKELIHOOD_LABELS[L]}</th>']
        for I in range(1, 6):
            level = engine.risk_level(L, I)
            ids = ", ".join(html.escape(i) for i in cells.get((L, I), []))
            tds.append(f'<td style="background:{LEVEL_COLOURS[level]}" title="{level} risk">{ids}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    footer = "".join(f'<th class="axis">{engine.IMPACT_LABELS[I]}</th>' for I in range(1, 6))
    return (f'<figure><table class="grid">' + "".join(rows)
            + f'<tr><th class="axis"></th>{footer}</tr></table>'
            + f'<figcaption>{html.escape(caption)}<br><small>Rows: likelihood. Columns: impact.</small></figcaption></figure>')


def badge(level):
    # small coloured label for a risk level, e.g. "High"
    text = "#fff" if level in ("Very High", "Very Low") else "#111"   # white text on the dark colours so it can be read
    return f'<span class="badge" style="background:{LEVEL_COLOURS[level]};color:{text}">{level}</span>'


def write_html(results, path, source_name):
    # create the full report page (cover, 6 sections, tables and heat maps)
    ranked = sorted(results, key=rank_key, reverse=True)
    counts_before = {lvl: sum(r["inherent_level"] == lvl for r in results) for lvl in LEVEL_ORDER}
    counts_after = {lvl: sum(r["residual_level"] == lvl for r in results) for lvl in LEVEL_ORDER}
    total_before = sum(r["ale_before"] for r in results)
    total_after = sum(r["ale_after"] for r in results)
    reduction = 0 if total_before == 0 else (total_before - total_after) / total_before * 100
    top = ranked[0]
    e = html.escape

    # Table 1 in the report: how many risks at each level, before and after
    count_rows = "".join(
        f"<tr><td>{badge(l)}</td><td class='c'>{counts_before[l]}</td><td class='c'>{counts_after[l]}</td></tr>"
        for l in LEVEL_ORDER)

    # Table 2: the full risk register
    register_rows = []
    for n, r in enumerate(ranked, start=1):
        register_rows.append(
            "<tr>"
            f"<td class='c'>{n}</td>"
            f"<td>{e(r['id'])}</td>"
            f"<td><b>{e(r['asset'])}</b><br><small>{e(r['category'])}</small></td>"
            f"<td>{e(r['threat'])}<br><small>Vulnerability: {e(r['vulnerability'])}</small></td>"
            f"<td>{e(r['existing_control'])}<br><small>{r['control_effectiveness']:.0f}% effective</small></td>"
            f"<td class='c'>{badge(r['inherent_level'])}</td>"
            f"<td class='c'>{badge(r['residual_level'])}</td>"
            f"<td class='num'>{rm(r['ale_before'])}<br><small>after: {rm(r['ale_after'])}</small></td>"
            "</tr>")

    # Table 3: suggested NIST response for each risk
    response_rows = "".join(
        "<tr>"
        f"<td>{e(r['id'])}</td><td>{e(r['asset'])}</td><td class='c'>{badge(r['residual_level'])}</td>"
        f"<td>{e(r['treatment'])}<br><small>{e(r['meaning'])}</small></td><td>{e(r['owner'])}</td>"
        "</tr>" for r in ranked)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(REPORT_TITLE)}</title>
<style>
 * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
 @page {{ size: A4; margin: 15mm; }}
 tr, figure {{ break-inside: avoid; }}
 h2 {{ break-after: avoid; }}
 body {{ font-family: Arial, Helvetica, sans-serif; background:#e9e9e9; margin:0; color:#222; line-height:1.5; }}
 .page {{ background:#fff; max-width:900px; margin:24px auto; padding:48px 56px; box-shadow:0 0 6px rgba(0,0,0,.15); }}
 .cover {{ text-align:center; border-bottom:2px solid #222; padding-bottom:20px; margin-bottom:28px; }}
 .cover h1 {{ font-family: Georgia, 'Times New Roman', serif; font-size:28px; margin:0 0 6px; letter-spacing:1px; text-transform:uppercase; }}
 .cover .sub {{ font-size:16px; margin:0 0 16px; color:#444; }}
 .cover table {{ margin:0 auto; font-size:14px; }}
 .cover td {{ padding:2px 10px; text-align:left; }}
 h2 {{ font-family: Georgia, 'Times New Roman', serif; font-size:20px; border-bottom:1px solid #999; padding-bottom:4px; margin-top:36px; }}
 p {{ font-size:14px; }}
 table.data {{ width:100%; border-collapse:collapse; font-size:13px; margin:8px 0 4px; }}
 table.data th {{ background:#eee; border:1px solid #999; padding:6px; text-align:left; }}
 table.data td {{ border:1px solid #999; padding:6px; vertical-align:top; }}
 table.data small {{ color:#555; }}
 .c {{ text-align:center; }}
 .num {{ white-space:nowrap; }}
 .caption {{ font-size:12px; font-style:italic; text-align:center; margin:4px 0 16px; }}
 .badge {{ color:#111; padding:1px 7px; border-radius:3px; font-size:11px; font-weight:bold; white-space:nowrap; }}
 .maps {{ display:flex; gap:24px; justify-content:center; flex-wrap:wrap; }}
 figure {{ margin:0; }}
 figcaption {{ font-size:12px; font-style:italic; text-align:center; margin-top:6px; }}
 table.grid {{ border-collapse:collapse; }}
 table.grid td {{ width:62px; height:40px; text-align:center; font-size:11px; font-weight:bold; border:1px solid #fff; }}
 table.grid th.axis {{ font-size:10px; font-weight:normal; padding:2px 4px; }}
 ul {{ font-size:14px; }}
 code {{ background:#f2f2f2; padding:1px 4px; }}
 .footer {{ text-align:center; font-size:11px; color:#666; margin-top:40px; border-top:1px solid #ccc; padding-top:8px; }}
 @media print {{
   body {{ background:#fff; }}
   .page {{ box-shadow:none; margin:0; max-width:none; padding:0; }}
   table.data {{ font-size:11px; width:99%; }}
   table.grid td {{ width:50px; height:32px; }}
   h2 {{ margin-top:24px; }}
 }}
</style></head><body><div class="page">

<div class="cover">
 <h1>{e(REPORT_TITLE)}</h1>
 <p class="sub">{e(SCENARIO)}</p>
 <table>
  <tr><td><b>Prepared by</b></td><td>{e(AUTHOR)}</td></tr>
  <tr><td><b>Programme</b></td><td>{e(PROGRAMME)}</td></tr>
  <tr><td><b>Date</b></td><td>{datetime.now():%d %B %Y}</td></tr>
  <tr><td><b>Method</b></td><td>NIST SP 800-30 Rev. 1</td></tr>
  <tr><td><b>Data file</b></td><td>{e(source_name)} ({len(results)} risks)</td></tr>
 </table>
</div>

<h2>1. Executive summary</h2>
<p>This assessment covers {len(results)} risks. Existing controls reduce the expected yearly loss
(ALE) from <b>{rm(total_before)}</b> to <b>{rm(total_after)}</b>, a reduction of {reduction:.0f}%.
The highest remaining risk is <b>{e(top['asset'])}</b> ({e(top['id'])}), rated
<b>{top['residual_level']}</b> after controls.</p>
<table class="data" style="width:60%;margin:0 auto">
 <tr><th>Risk level (NIST)</th><th class="c">Before controls</th><th class="c">After controls</th></tr>
 {count_rows}
</table>
<p class="caption">Table 1: Number of risks at each level</p>

<h2>2. Risk heat maps</h2>
<div class="maps">
 {heatmap_html(results, "likelihood", "Figure 1: Inherent risk (before controls)")}
 {heatmap_html(results, "residual_likelihood", "Figure 2: Residual risk (after controls)")}
</div>

<h2>3. Risk register</h2>
<table class="data">
<tr><th>#</th><th>ID</th><th>Asset</th><th>Threat</th><th>Existing control</th>
<th>Inherent</th><th>Residual</th><th>ALE / year</th></tr>
{''.join(register_rows)}
</table>
<p class="caption">Table 2: Risk register, highest residual risk first</p>

<h2>4. Suggested risk responses</h2>
<p>Responses use the five risk response types in NIST SP 800-39 (accept, avoid, mitigate, share,
transfer). Level meanings follow NIST SP 800-30 Table I-3. The final choice depends on the
organisation's risk tolerance.</p>
<table class="data">
<tr><th>ID</th><th>Asset</th><th>Residual</th><th>Suggested response</th><th>Owner</th></tr>
{response_rows}
</table>
<p class="caption">Table 3: Suggested response for each risk</p>

<h2>5. Methodology</h2>
<ul>
 <li>Likelihood and impact are rated on the NIST scale: 1 Very Low, 2 Low, 3 Moderate, 4 High, 5 Very High.</li>
 <li>Impact is the highest of the Confidentiality, Integrity and Availability ratings.</li>
 <li>The risk level is looked up in NIST SP 800-30 Table I-2 (likelihood and impact combined).</li>
 <li>Residual likelihood = <code>ceil(likelihood x (1 - control effectiveness))</code>, minimum 1.</li>
 <li>Yearly loss: <code>SLE = asset value x exposure factor</code>, <code>ALE = SLE x ARO</code>,
     ALE after controls = ALE x (1 - control effectiveness).</li>
 <li>All ratings and values are estimates for a fictional case study.</li>
</ul>

<h2>6. References</h2>
<ul>
 <li>NIST (2012). SP 800-30 Rev. 1, <i>Guide for Conducting Risk Assessments</i>.</li>
 <li>NIST (2011). SP 800-39, <i>Managing Information Security Risk</i>.</li>
 <li>ISO/IEC 27005:2022, <i>Guidance on managing information security risks</i>.</li>
</ul>

<div class="footer">{e(REPORT_TITLE)} &middot; {e(AUTHOR)}</div>
</div></body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


# ===== Start of the program =====

def main(argv=None):
    # 1. read the CSV  2. calculate  3. print summary  4. save HTML and CSV
    parser = argparse.ArgumentParser(description="Assess a cybersecurity risk register (CSV).")
    parser.add_argument("register", nargs="?", default=os.path.join("data", "sample_register.csv"),
                        help="path to the risk register CSV (default: data/sample_register.csv)")
    parser.add_argument("-o", "--output", default="reports", help="output folder (default: reports)")
    args = parser.parse_args(argv)

    results = load_register(args.register)
    os.makedirs(args.output, exist_ok=True)
    html_path = os.path.join(args.output, "risk_report.html")
    csv_path = os.path.join(args.output, "risk_results.csv")

    print_summary(results)
    write_html(results, html_path, os.path.basename(args.register))
    write_csv(results, csv_path)
    print(f"\nHTML report : {html_path}")
    print(f"CSV results : {csv_path}")


if __name__ == "__main__":
    main()
