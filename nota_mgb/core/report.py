"""Relatório HTML da avaliação (uma camada ou o projeto), para anexar a entregas.

HTML autocontido (sem CSS/JS externo); abre em qualquer navegador e pode ser
impresso em PDF pelo próprio navegador.
"""

from __future__ import annotations

import datetime as _dt
from html import escape
from typing import Any, Dict, List, Optional

SELO_COLORS = {"Excelente": "#1a7f37", "Conforme": "#2f6fb0", "Não conforme": "#b42318"}

_STYLE = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2328;
max-width:860px;margin:32px auto;padding:0 16px;line-height:1.45}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #d0d7de;padding-bottom:4px}
.meta{color:#59636e;font-size:13px}.score{font-size:40px;font-weight:700;margin:16px 0 0}
.selo{display:inline-block;color:#fff;border-radius:4px;padding:2px 10px;font-weight:600;font-size:14px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f6f8fa}td.num{text-align:right;white-space:nowrap}.ok{color:#1a7f37}.bad{color:#b42318}
footer{margin-top:32px;color:#59636e;font-size:12px}
"""


def _selo(selo: str) -> str:
    color = SELO_COLORS.get(selo, "#59636e")
    return f'<span class="selo" style="background:{color}">{escape(selo)}</span>'


def _page(title: str, body: str, generated: str) -> str:
    return (
        '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head><body>\n{body}\n"
        f"<footer>Gerado em {escape(generated)} pelo plugin Nota MGB para QGIS "
        "(Rafael Dantas de Morais, Ibexdev). Régua: Perfil MGB 2.0, IBGE/DSG 2021.</footer>\n</body></html>\n"
    )


def _now(now: Optional[_dt.datetime]) -> str:
    return (now or _dt.datetime.now()).strftime("%d/%m/%Y %H:%M")


def layer_report(
    layer_name: str,
    result: Dict[str, Any],
    quality_labels: Dict[str, Dict[str, Any]],
    now: Optional[_dt.datetime] = None,
) -> str:
    rows: List[str] = []
    for issue in result["issues"]:
        kind = "Falta" if issue["problem"] == "missing" else "Valor inválido"
        rows.append(
            f"<tr><td>{escape(issue['label'])}</td><td class=\"bad\">{kind}</td>"
            f"<td>{escape(issue['message'])}</td><td class=\"num\">Q{issue['quadro']} l.{issue['linha']}</td></tr>"
        )
    issues_html = (
        "<table><tr><th>Elemento</th><th>Situação</th><th>Detalhe</th><th>Norma</th></tr>"
        + "".join(rows)
        + "</table>"
        if rows
        else '<p class="ok">Todos os elementos obrigatórios estão preenchidos e válidos.</p>'
    )

    quality_rows = []
    for name, spec in quality_labels.items():
        ok = result["quality_checks"].get(name, False)
        mark = '<span class="ok">atendido</span>' if ok else '<span class="bad">não atendido</span>'
        points = spec["weight"] if ok else 0
        quality_rows.append(
            f"<tr><td>{escape(spec['description'])}</td><td>{mark}</td>"
            f"<td class=\"num\">{points}/{spec['weight']}</td></tr>"
        )

    body = (
        f"<h1>Avaliação de metadados — {escape(layer_name)}</h1>"
        f"<div class=\"meta\">{escape(result['resource_label'])} · "
        f"{result['satisfied_required']} de {result['required_fields']} obrigatórios atendidos</div>"
        f"<div class=\"score\">{result['total_score']:.0f}/100</div>"
        f"<p>{_selo(result['selo'])} Conformidade {result['conformity_score']:.1f}/70 · "
        f"Qualidade {result['quality_score']}/30</p>"
        f"<h2>Elementos obrigatórios</h2>{issues_html}"
        "<h2>Qualidade (além da norma)</h2>"
        "<table><tr><th>Critério</th><th>Situação</th><th>Pontos</th></tr>"
        + "".join(quality_rows)
        + "</table>"
    )
    return _page(f"Nota MGB — {layer_name}", body, _now(now))


def project_report(report: Dict[str, Any], now: Optional[_dt.datetime] = None) -> str:
    rows = []
    for row in report["layers"]:
        pending = len(row["missing_required"]) + len(row["invalid_required_values"])
        rows.append(
            f"<tr><td>{escape(row['layer_name'])}</td><td class=\"num\">{row['total_score']:.0f}</td>"
            f"<td>{_selo(row['selo'])}</td><td class=\"num\">{pending}</td>"
            f"<td>{escape(row['resource_label'])}</td></tr>"
        )
    summary = report["summary"]
    body = (
        "<h1>Avaliação de metadados do projeto</h1>"
        f"<div class=\"meta\">{summary['total_layers']} camada(s) · {summary['conform_layers']} conforme(s) · "
        f"{summary['non_conform_layers']} não conforme(s)</div>"
        "<h2>Camadas (da pior para a melhor)</h2>"
        "<table><tr><th>Camada</th><th>Nota</th><th>Selo</th><th>Pendências</th><th>Tipo de recurso</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return _page("Nota MGB — projeto", body, _now(now))


__all__ = ["layer_report", "project_report"]
