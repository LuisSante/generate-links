# https://datajud-wiki.cnj.jus.br/api-publica/acesso

import json, time, argparse, sys
import requests

API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# CNJ subject codes (confirmed on TJBA):
#   7772  Credit Card
#   9585  Credit Card (variant)
#   11806 Payroll loan (RMC / payroll credit card usually falls here)
DEFAULT_SUBJECTS = [7772, 9585]

# Public consultation portal per system (verified TJBA domains).
PORTALS = {
    "tjba": {
        "Eproc": "https://eproc1g.tjba.jus.br/eproc/externo_controlador.php?acao=processo_consulta_publica",
        "PJe":   "https://pje.tjba.jus.br/pje/ConsultaPublica/listView.seam",
    },
}

def endpoint(court):
    return f"https://api-publica.datajud.cnj.jus.br/api_publica_{court}/_search"

def build_query(subjects, system, size, search_after):
    must = [{"terms": {"assuntos.codigo": subjects}}]
    if system:
        must.append({"term": {"sistema.nome.keyword": system}})
    query = {
        "size": size,
        "sort": [{"@timestamp": {"order": "asc"}},
                 {"numeroProcesso.keyword": {"order": "asc"}},
                 {"grau.keyword": {"order": "asc"}}],
        "query": {"bool": {"must": must}},
        "_source": ["numeroProcesso", "classe.nome", "assuntos.nome",
                    "assuntos.codigo", "dataAjuizamento", "sistema.nome",
                    "nivelSigilo", "orgaoJulgador.nome", "tribunal", "grau"],
    }
    if search_after:
        query["search_after"] = search_after
    return query

def consult_url(court, system):
    return PORTALS.get(court, {}).get(system, "")

def format_cnj(number):
    number = "".join(filter(str.isdigit, str(number))).zfill(20)
    return f"{number[0:7]}-{number[7:9]}.{number[9:13]}.{number[13:14]}.{number[14:16]}.{number[16:20]}"

def name_of(value):
    # Some fields (classe/orgaoJulgador/sistema) come as dict OR list-of-dicts.
    if isinstance(value, list):
        value = value[0] if value else {}
    if isinstance(value, dict):
        return value.get("nome")
    return None

def names_of(items):
    out = []
    for a in items or []:
        if isinstance(a, dict):
            out.append(a.get("nome"))
    return out

def record(court, source):
    number = source.get("numeroProcesso")
    system = name_of(source.get("sistema"))
    return {
        "numero_processo": format_cnj(number),
        "numero_raw": number,
        "tribunal": source.get("tribunal"),
        "grau": source.get("grau"),
        "sistema": system,
        "nivel_sigilo": source.get("nivelSigilo"),
        "classe": name_of(source.get("classe")),
        "assuntos": names_of(source.get("assuntos")),
        "orgao_julgador": name_of(source.get("orgaoJulgador")),
        "data_ajuizamento": source.get("dataAjuizamento"),
        "url_consulta": consult_url(court, system),
        "fonte": "datajud",
        "coletado_em": time.strftime("%Y-%m-%d"),
    }

def post_with_retry(session, url, body, tries=4):
    for attempt in range(tries):
        try:
            resp = session.post(url, data=json.dumps(body), timeout=90)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            wait = 2 * (attempt + 1)
            print(f"  [retry {attempt+1}/{tries}] {e} -> waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    return None

def run(court, subjects, system, limit, page_size, delay, out):
    session = requests.Session()
    session.headers.update({"Authorization": f"APIKey {API_KEY}",
                            "Content-Type": "application/json"})
    url = endpoint(court)
    search_after, written = None, 0
    with open(out, "w", encoding="utf-8") as f:
        while limit is None or written < limit:
            size = page_size if limit is None else min(page_size, limit - written)
            data = post_with_retry(session, url, build_query(subjects, system, size, search_after))
            if data is None:
                print("  [abort] API failed after retries", file=sys.stderr); break
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break
            for hit in hits:
                f.write(json.dumps(record(court, hit["_source"]), ensure_ascii=False) + "\n")
            written += len(hits)
            f.flush()
            search_after = hits[-1].get("sort")
            print(f"  ... {written} written", file=sys.stderr)
            time.sleep(delay)
    print(f"\n{written} records saved in {out}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--court", default="tjba")
    parser.add_argument("--subjects", type=int, nargs="*", default=DEFAULT_SUBJECTS)
    parser.add_argument("--system", default=None, help="Eproc | PJe (blank = all)")
    parser.add_argument("--max", type=int, default=None, help="blank = all matching")
    parser.add_argument("--page", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--out", default="links.jsonl")
    args = parser.parse_args()
    print(f"court={args.court} subjects={args.subjects} system={args.system} target={args.max}", file=sys.stderr)
    run(args.court, args.subjects, args.system, args.max, args.page, args.delay, args.out)

if __name__ == "__main__":
    main()
