import json, time, argparse, sys
import requests

APIKEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# Assuntos CNJ ligados a cartão de crédito / consignado (TJBA confirmado):
#   7772  Cartão de Crédito        9585  Cartão de Crédito (variante)
#   11806 Empréstimo consignado   (RMC / cartão consignado costuma cair aqui)
DEFAULT_ASSUNTOS = [7772, 9585, 11806]

# Pós-filtro textual: mantém só o que soa a cartão/consignado/RMC
KW = ["cart", "consign", "rmc", "margem"]

def endpoint(trib):
    return f"https://api-publica.datajud.cnj.jus.br/api_publica_{trib}/_search"

def build_query(assuntos, size, search_after):
    q = {
        "size": size,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "query": {"terms": {"assuntos.codigo": assuntos}},
        "_source": ["numeroProcesso", "classe.nome", "assuntos.nome",
                    "assuntos.codigo", "dataAjuizamento",
                    "orgaoJulgador.nome", "tribunal", "grau"],
    }
    if search_after:
        q["search_after"] = search_after
    return q

def consulta_url(trib, numero):
    # URL de consulta pública do processo (abre no portal do tribunal; alguns
    # exigem CAPTCHA/sessão para exibir os autos). O número CNJ é o que importa.
    dom = {"tjba": "https://projudi.tjba.jus.br/projudi/"}.get(trib, "")
    return dom

def keep(src):
    txt = " ".join(a.get("nome", "") for a in src.get("assuntos", [])).lower()
    txt += " " + (src.get("classe", {}) or {}).get("nome", "").lower()
    return any(k in txt for k in KW)

def fmt_cnj(n):
    n = "".join(filter(str.isdigit, str(n))).zfill(20)
    return f"{n[0:7]}-{n[7:9]}.{n[9:13]}.{n[13:14]}.{n[14:16]}.{n[16:20]}"

def run(trib, assuntos, maximo, page, delay, out):
    sess = requests.Session()
    sess.headers.update({"Authorization": f"APIKey {APIKEY}",
                         "Content-Type": "application/json"})
    url = endpoint(trib)
    after, coletados, vistos = None, [], 0
    while len(coletados) < maximo:
        body = build_query(assuntos, min(page, maximo - len(coletados) + page), after)
        try:
            r = sess.post(url, data=json.dumps(body), timeout=60)
            r.raise_for_status()
        except Exception as e:
            print(f"[erro] {e}", file=sys.stderr); break
        hits = r.json().get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            vistos += 1
            s = h["_source"]
            if not keep(s):
                continue
            num = s.get("numeroProcesso")
            coletados.append({
                "numero_processo": fmt_cnj(num),
                "numero_raw": num,
                "tribunal": s.get("tribunal"),
                "grau": s.get("grau"),
                "classe": (s.get("classe") or {}).get("nome"),
                "assuntos": [a.get("nome") for a in s.get("assuntos", [])],
                "orgao_julgador": (s.get("orgaoJulgador") or {}).get("nome"),
                "data_ajuizamento": s.get("dataAjuizamento"),
                "url_consulta": consulta_url(trib, num),
                "fonte": "datajud",
                "coletado_em": time.strftime("%Y-%m-%d"),
            })
            if len(coletados) >= maximo:
                break
        after = hits[-1].get("sort")
        print(f"  ... {len(coletados)} mantidos / {vistos} vistos", file=sys.stderr)
        time.sleep(delay)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(coletados, f, ensure_ascii=False, indent=1)
    print(f"\n{len(coletados)} processos gravados em {out}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tribunal", default="tjba")
    ap.add_argument("--assuntos", type=int, nargs="*", default=DEFAULT_ASSUNTOS)
    ap.add_argument("--max", type=int, default=2000)
    ap.add_argument("--page", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--out", default="links.json")
    a = ap.parse_args()
    print(f"Tribunal={a.tribunal} assuntos={a.assuntos} meta={a.max}", file=sys.stderr)
    run(a.tribunal, a.assuntos, a.max, a.page, a.delay, a.out)

if __name__ == "__main__":
    main()
