"""Baixa uma amostra de metadados do catálogo da INDE para calibrar a nota.

Uso: python3 scripts/amostra_inde.py <pasta_saida> [n_por_schema]
Script de desenvolvimento (não vai no plugin).
"""
import json
import os
import random
import sys
import urllib.request

BASE = "https://metadados.inde.gov.br/geonetwork/srv"
SCHEMAS = ["iso19115-3.mgb", "iso19139.mgbcompleto", "iso19139.mgbsumarizado"]


def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "nota-mgb-calibracao"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 - URL fixa https
        return resp.read()


def main():
    out, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10
    random.seed(42)
    for schema in SCHEMAS:
        os.makedirs(os.path.join(out, schema), exist_ok=True)
        q = json.loads(get(f"{BASE}/por/q?_content_type=json&fast=index&from=1&to=1&_schema={schema}"))
        q = q[0] if isinstance(q, list) else q
        total = int(q["summary"]["@count"])
        got = 0
        for start in random.sample(range(1, total), n * 3):
            if got >= n:
                break
            page = json.loads(get(f"{BASE}/por/q?_content_type=json&fast=index&from={start}&to={start}&_schema={schema}"))
            page = page[0] if isinstance(page, list) else page
            meta = page.get("metadata")
            meta = meta[0] if isinstance(meta, list) else meta
            uuid = (meta or {}).get("geonet:info", {}).get("uuid")
            if not uuid:
                continue
            xml = get(f"{BASE}/api/records/{uuid}/formatters/xml", "application/xml")
            with open(os.path.join(out, schema, f"{uuid}.xml"), "wb") as fh:
                fh.write(xml)
            got += 1
        print(schema, total, "registros; baixados", got)


if __name__ == "__main__":
    main()
