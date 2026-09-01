# Step 2 - Filter out archived cases.
# Input : a JSONL from step 1 (eproc.jsonl / pje.jsonl)
# Output: <name>_activos.jsonl  (arquivado=false)  +  <name>_arquivados.jsonl
#
# The step-1 files do NOT carry `movimentos`, so we re-query DataJud in batches
# only to learn which case numbers have movement code 246 (Arquivamento).
#
# Usage:
#   python3 filtrar_activos.py ../eproc.jsonl --court tjba
#   python3 filtrar_activos.py ../pje.jsonl   --court tjba --batch 200

import json, sys, time, argparse, os
import requests

API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
ARQUIVAMENTO_COD = 246

def endpoint(court):
    return f"https://api-publica.datajud.cnj.jus.br/api_publica_{court}/_search"

def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def archived_set(session, url, numbers, batch, delay):
    """Return the set of numeroProcesso that have an Arquivamento movement."""
    archived = set()
    nums = list(numbers)
    for i in range(0, len(nums), batch):
        chunk = nums[i:i + batch]
        body = {
            "size": 0,
            "query": {"bool": {"must": [
                {"terms": {"numeroProcesso": chunk}},
                {"term": {"movimentos.codigo": ARQUIVAMENTO_COD}},
            ]}},
            "aggs": {"arq": {"terms": {"field": "numeroProcesso.keyword",
                                        "size": len(chunk)}}},
        }
        for attempt in range(4):
            try:
                r = session.post(url, data=json.dumps(body), timeout=90)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                print(f"  [retry {attempt+1}] {e}", file=sys.stderr)
                time.sleep(2 * (attempt + 1))
        else:
            print("  [abort] batch failed", file=sys.stderr); continue
        for b in data.get("aggregations", {}).get("arq", {}).get("buckets", []):
            archived.add(b["key"])
        print(f"  ... {min(i+batch, len(nums))}/{len(nums)} números verificados "
              f"({len(archived)} archivados)", file=sys.stderr)
        time.sleep(delay)
    return archived

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--court", default="tjba")
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.2)
    a = ap.parse_args()

    rows = load(a.input)
    numbers = {r["numero_raw"] for r in rows}
    print(f"{len(rows)} filas | {len(numbers)} números únicos", file=sys.stderr)

    session = requests.Session()
    session.headers.update({"Authorization": f"APIKey {API_KEY}",
                            "Content-Type": "application/json"})
    archived = archived_set(session, endpoint(a.court), numbers, a.batch, a.delay)

    base = os.path.splitext(os.path.basename(a.input))[0]
    out_act = f"{base}_activos.jsonl"   # escreve na pasta atual
    out_arq = f"{base}_arquivados.jsonl"
    na = nr = 0
    with open(out_act, "w", encoding="utf-8") as fa, \
         open(out_arq, "w", encoding="utf-8") as fr:
        for r in rows:
            r["arquivado"] = r["numero_raw"] in archived
            line = json.dumps(r, ensure_ascii=False) + "\n"
            if r["arquivado"]:
                fr.write(line); nr += 1
            else:
                fa.write(line); na += 1
    print(f"\nactivos:    {na}  -> {out_act}", file=sys.stderr)
    print(f"arquivados: {nr}  -> {out_arq}", file=sys.stderr)

if __name__ == "__main__":
    main()
