# https://datajud-wiki.cnj.jus.br/api-publica/acesso

import json, time, argparse, sys
import requests

API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# CNJ subject codes tied to credit card / payroll loan (TJBA confirmed):
#   7772  Credit Card
#   9585  Credit Card (variant)
#   11806 Payroll loan (RMC / payroll credit card usually falls here)
DEFAULT_SUBJECTS = [7772, 9585, 11806]

# Textual post-filter: keep only what looks like card / payroll / RMC
KEYWORDS = ["cart", "consign", "rmc", "margem"]

def endpoint(court):
    return f"https://api-publica.datajud.cnj.jus.br/api_publica_{court}/_search"

def build_query(subjects, size, search_after):
    query = {
        "size": size,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {"terms": {"assuntos.codigo": subjects}},
        "_source": ["numeroProcesso", "classe.nome", "assuntos.nome",
                    "assuntos.codigo", "dataAjuizamento",
                    "orgaoJulgador.nome", "tribunal", "grau"],
    }
    if search_after:
        query["search_after"] = search_after
    return query

def consult_url(court, number):
    domain = {"tjba": "https://projudi.tjba.jus.br/projudi/"}.get(court, "")
    return domain

def keep(source):
    text = " ".join(a.get("nome", "") for a in source.get("assuntos", [])).lower()
    text += " " + (source.get("classe", {}) or {}).get("nome", "").lower()
    return any(k in text for k in KEYWORDS)

def format_cnj(number):
    number = "".join(filter(str.isdigit, str(number))).zfill(20)
    return f"{number[0:7]}-{number[7:9]}.{number[9:13]}.{number[13:14]}.{number[14:16]}.{number[16:20]}"

def run(court, subjects, limit, page_size, delay, out):
    session = requests.Session()
    session.headers.update({"Authorization": f"APIKey {API_KEY}",
                            "Content-Type": "application/json"})
    url = endpoint(court)
    search_after, collected, seen = None, [], 0
    while len(collected) < limit:
        body = build_query(subjects, page_size, search_after)
        try:
            resp = session.post(url, data=json.dumps(body), timeout=60)
            resp.raise_for_status()
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr); break
        hits = resp.json().get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            seen += 1
            source = hit["_source"]
            if not keep(source):
                continue
            number = source.get("numeroProcesso")
            collected.append({
                "numero_processo": format_cnj(number),
                "numero_raw": number,
                "tribunal": source.get("tribunal"),
                "grau": source.get("grau"),
                "classe": (source.get("classe") or {}).get("nome"),
                "assuntos": [a.get("nome") for a in source.get("assuntos", [])],
                "orgao_julgador": (source.get("orgaoJulgador") or {}).get("nome"),
                "data_ajuizamento": source.get("dataAjuizamento"),
                "url_consulta": consult_url(court, number),
                "fonte": "datajud",
                "coletado_em": time.strftime("%Y-%m-%d"),
            })
            if len(collected) >= limit:
                break
        search_after = hits[-1].get("sort")
        print(f"  ... {len(collected)} kept / {seen} seen", file=sys.stderr)
        time.sleep(delay)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(collected, f, ensure_ascii=False, indent=1)
    print(f"\n{len(collected)} saved in {out}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--court", default="tjba")
    parser.add_argument("--subjects", type=int, nargs="*", default=DEFAULT_SUBJECTS)
    parser.add_argument("--max", type=int, default=2000)
    parser.add_argument("--page", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--out", default="links.json")
    args = parser.parse_args()
    print(f"court={args.court} subjects={args.subjects} target={args.max}", file=sys.stderr)
    run(args.court, args.subjects, args.max, args.page, args.delay, args.out)

if __name__ == "__main__":
    main()
