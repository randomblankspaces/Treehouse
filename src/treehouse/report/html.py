"""Static HTML report (one file per run) and the generic chip renderer.

Inline CSS, no JS, every value through ``html.escape``, never image bytes. A banner is driven by the
bundle's ``synthetic`` flag and every synthetic row carries a SYNTHETIC chip. Every number sits under an
element that names its provenance: ``data-tier`` (a Treehouse tier, ``agent-claim`` for the agent's own
figures, ``tool-record`` for tool outputs), ``data-id`` (ids, dates, hashes) or ``data-card`` (verbatim
task-card text). A test (I6) walks the HTML and enforces it.
"""

from __future__ import annotations

from html import escape

from treehouse.schemas.bundle import ReportBundle
from treehouse.schemas.numbers import Tier, TypedNumber

BANNER = "SYNTHETIC DEMO DATA"
CSS = """
body{font:14px/1.45 system-ui,sans-serif;margin:0;padding:0 16px 32px;color:#1d2330;background:#fbfbf8}
main{max-width:1100px;margin:0 auto}
.banner{background:#7a1f1f;color:#fff;font-weight:700;padding:8px 16px;margin:0 -16px 16px;letter-spacing:.04em}
h1{font-size:22px;margin:12px 0 4px} h2{font-size:17px;margin:24px 0 8px;border-bottom:1px solid #ddd}
table{border-collapse:collapse;width:100%;font-size:12.5px;display:block;overflow-x:auto}
th,td{border-bottom:1px solid #e3e3dc;padding:3px 6px;text-align:left;vertical-align:top;white-space:nowrap}
.chip{display:inline-block;border-radius:9px;padding:0 7px;font-size:11px;background:#e8ecf3;color:#24324a}
.chip.t-ABSTAINED{background:#f1e4e4;color:#6b1d1d} .chip.t-MEASURED{background:#e4efe7;color:#1d4b2c}
.chip.syn{background:#7a1f1f;color:#fff;font-weight:600}
.num{font-variant-numeric:tabular-nums;font-weight:600}
.verdict{font-size:16px;padding:8px 12px;background:#f3f1ea;border-left:4px solid #7a1f1f}
.muted{color:#666} code{font-size:12px}
"""


def _e(x: object) -> str:
    return escape(str(x), quote=True)


def ident(x: object) -> str:
    return f'<code data-id="1">{_e(x)}</code>'


def fmt_value(tn: TypedNumber) -> str:
    v = tn.value
    if v is None:
        return "not issued"
    if tn.type in ("count", "tokens", "bytes", "flag"):
        return f"{int(v):,}"
    if tn.type == "usd":
        return f"${v:,.4f}"
    if tn.type == "proportion":
        return f"{v:.3f}"
    return f"{v:g}"


def chip_html(tn: TypedNumber) -> str:
    """The generic chip: plain-English tier label plus SYNTHETIC / recorded / modelled bytes."""
    t = tn.tier.value
    return (f'<span class="chip t-{_e(t)}" data-tier="{_e(t)}" title="{_e(tn.chip_hover())}">'
            f"{_e(tn.chip())}</span>")


def num_html(tn: TypedNumber) -> str:
    return (f'<span class="num" data-tier="{_e(tn.tier.value)}">{_e(fmt_value(tn))}</span> {chip_html(tn)}')


def syn_chip(synthetic: bool) -> str:
    return '<span class="chip syn">SYNTHETIC</span>' if synthetic else ""


def _numbers_table(nums: dict[str, TypedNumber]) -> str:
    rows = "".join(f"<tr><td>{_e(k)}</td><td>{num_html(v)}</td>"
                   f'<td data-tier="{_e(v.tier.value)}" class="muted">n={_e(v.n)}</td></tr>'
                   for k, v in sorted(nums.items()))
    return f"<table><tr><th>metric</th><th>value</th><th>denominator</th></tr>{rows}</table>"


def _panel(title: str, p) -> str:
    out = f"<h2>{_e(title)}</h2>"
    if p.no_grade_reason:
        out += f'<p class="muted" data-tier="{Tier.ABSTAINED.value}">{_e(p.no_grade_reason)}</p>'
    if p.numbers:
        out += _numbers_table(p.numbers)
    return out


def _claims(b: ReportBundle) -> str:
    led = {lg.claim_id: lg for lg in b.ledgers}
    note = b.card_summary.get("row_note", "")
    head = ("<tr><th>claim</th><th>step</th><th>class</th><th>status</th><th>lon, lat (agent's claim)</th>"
            "<th>confidence (agent's claim)</th><th>evidence</th><th>R1 R2 R4</th><th>ledger</th><th>data</th></tr>")
    rows = []
    for c in b.claims:
        lg = led.get(c.claim_id)
        rules = " ".join(f"{r.check_id}:{r.result}" + (f"({r.code})" if r.code else "")
                         for r in (lg.results if lg else []))
        lon, lat = c.geometry.coordinates
        rows.append(
            f'<tr data-row="claim" data-synthetic="{str(c.synthetic).lower()}"><td>{ident(c.claim_id)}</td>'
            f"<td>{_e(c.step_id)}</td><td>{_e(c.cls)}</td><td>{_e(c.status)}</td>"
            f'<td data-tier="agent-claim">{lon:.6f}, {lat:.6f}</td><td data-tier="agent-claim">{c.confidence:.2f}</td>'
            f"<td>{' '.join(ident(r.result_id) for r in c.evidence_refs) or '-'}</td>"
            f'<td data-id="1">{_e(rules)}</td><td>{_e(lg.resolved if lg else "unchecked")}</td>'
            f"<td>{syn_chip(c.synthetic)} {_e(note) if c.synthetic else ''}</td></tr>")
    return f"<h2>Claims and checks</h2><table>{head}{''.join(rows)}</table>"


def _evidence(b: ReportBundle) -> str:
    if not b.evidence:
        return ""
    head = ("<tr><th>result</th><th>scene</th><th>scene date</th><th>effective GSD m</th><th>bytes read</th>"
            "<th>bright/low-variance share</th><th>reader</th><th>data</th></tr>")
    rows = []
    for w in b.evidence:
        note = str(w.detail.get("note", ""))
        modelled = " modelled bytes" if w.detail.get("bytes_model") == "synthetic-overview-block-v1" else ""
        rows.append(
            f'<tr data-row="evidence" data-synthetic="{str(w.synthetic).lower()}"><td>{ident(w.result_id)}</td>'
            f"<td>{ident(w.scene_id)}</td><td>{ident(w.scene_datetime.date().isoformat())}</td>"
            f'<td data-tier="tool-record">{w.effective_gsd_m:g}</td>'
            f'<td data-tier="tool-record">{w.bytes_read:,}{_e(modelled)}</td>'
            f'<td data-tier="tool-record">{w.obscuration.bright_lowvar_fraction:.3f}</td><td>{_e(w.reader)}</td>'
            f"<td>{syn_chip(w.synthetic)} {_e(note)}</td></tr>")
    return f"<h2>Evidence windows (metadata only, no pixels)</h2><table>{head}{''.join(rows)}</table>"


def _trace(b: ReportBundle) -> str:
    rows = []
    for i, s in enumerate(b.trace_rows):
        a = s.attributes
        extra = a.get("treehouse.tool.block_reason") or (s.error.type if s.error else "")
        rows.append(f"<tr><td>{ident(i)}</td><td>{_e(s.op)}</td><td>{_e(s.name)}</td><td>{_e(s.status)}</td>"
                    f"<td>{ident(a.get('treehouse.tool.result_id', '')) if s.op == 'execute_tool' else ''}</td>"
                    f"<td>{_e(extra)}</td></tr>")
    return ("<h2>Trace timeline</h2><table><tr><th>seq</th><th>op</th><th>span</th><th>status</th><th>result</th>"
            f"<th>blocked / error</th></tr>{''.join(rows)}</table>")


def _passports(b: ReportBundle) -> str:
    out = []
    for p in b.passports:
        reasons = "; ".join(p.gate_reasons)
        out.append(f"<p><b>{_e(p.estimand.name)}</b> ({_e(p.estimand.step_id)}): {num_html(p.headline)} "
                   f"gate <b>{_e(p.gate)}</b> <span class='muted'>{_e(reasons)}</span></p>"
                   f"<p class='muted'>controls: {_e('; '.join(p.controls.unavailable))}</p>")
    return "<h2>Trust passport</h2>" + "".join(out)


def _summary_html(b: ReportBundle) -> str:
    f = b.facts
    parts = []
    if "claims" in f:
        parts.append(f"The agent recorded {num_html(f['claims'])} claims.")
    if "grounding_rate" in f:
        parts.append(f"Share of claims whose cited window contains the point (R4): {num_html(f['grounding_rate'])}.")
    if "forbidden_attempts" in f:
        parts.append(f"Forbidden-source attempts: {num_html(f['forbidden_attempts'])}.")
    if "bytes_read" in f:
        parts.append(f"Bytes read: {num_html(f['bytes_read'])}.")
    return f"<p>{' '.join(parts)}</p><p class='muted'>Template summary; narrative, not scored.</p>"


def render(b: ReportBundle) -> str:
    m, c = b.manifest_summary, b.card_summary
    verdict = b.passports[0] if b.passports else None
    banner = (f'<div class="banner">{BANNER}: every number, point, verdict and label on this page is synthetic.'
              "</div>") if b.synthetic else ""
    body = [
        banner,
        f"<h1>Run {ident(m.get('run_id', ''))}</h1>",
        f"<p class='muted'>task {ident(c.get('id', ''))} &middot; policy {_e(m.get('policy', ''))} &middot; "
        f"mode {_e(m.get('mode', ''))} &middot; stop {_e(m.get('stop', ''))} &middot; manifest "
        f"{ident(b.manifest_ref)}</p>",
        f"<p data-card='1'><b>{_e(c.get('title', ''))}</b>. {_e(c.get('synthetic_notice', ''))}</p>",
    ]
    if verdict is not None:
        body.append(f"<div class='verdict'>Verdict: <b>{_e(verdict.gate)}</b>. Trust headline "
                    f"{num_html(verdict.headline)}</div>")
    body += [_summary_html(b), _passports(b), _panel("How the agent worked", b.scorecard.process),
             _panel("What the agent understood", b.scorecard.understanding),
             _panel("What the agent produced", b.scorecard.output), _panel("Cost, speed and data", b.scorecard.cost),
             _claims(b), _evidence(b), _trace(b),
             f"<h2>Licence</h2><p>licence floor {ident(m.get('license_floor', ''))}</p>"]
    if m.get("nc_notice"):
        body.append(f"<p data-card='1'><b>{_e(m['nc_notice'])}</b></p>")
    title = f"Treehouse report: {m.get('run_id', '')}"
    return page(title, "".join(body))


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(title)}</title>'
            f"<style>{CSS}</style></head><body><main>{body}</main></body></html>\n")
