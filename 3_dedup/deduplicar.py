# Step 2 - Deduplicate by case number.
# One record per numero_processo. When a case has several DataJud docs
# (repeated same-grau, or multiple instances JE/G1/TR/G2), keep the
# first-instance one (where the contract is filed) and merge the subjects.
#
# Usage:
#   python3 deduplicar.py ../eproc.jsonl            # -> ../eproc_dedup.jsonl
#   python3 deduplicar.py ../pje.jsonl --out x.jsonl

import json, sys, argparse, os

# First instance first (contract lives there); appeals last.
GRAU_PRIORITY = {"JE": 0, "G1": 1, "TR": 2, "G2": 3}

def load(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def better(a, b):
    """Return the preferred record between a and b (lower grau priority wins)."""
    pa = GRAU_PRIORITY.get(a.get("grau"), 9)
    pb = GRAU_PRIORITY.get(b.get("grau"), 9)
    return a if pa <= pb else b

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.input))[0] + "_dedup.jsonl"

    best = {}          # numero_processo -> chosen record
    subjects = {}      # numero_processo -> set of subjects seen
    graus = {}         # numero_processo -> set of graus seen
    total = 0
    for r in load(a.input):
        total += 1
        num = r["numero_processo"]
        subjects.setdefault(num, set()).update(a for a in (r.get("assuntos") or []) if a)
        graus.setdefault(num, set()).add(r.get("grau"))
        best[num] = r if num not in best else better(best[num], r)

    with open(out, "w", encoding="utf-8") as f:
        for num, r in best.items():
            r = dict(r)
            r["assuntos"] = sorted(subjects[num])   # merged across duplicates
            r["graus"] = sorted(g for g in graus[num] if g)  # all instances seen
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"{total} filas -> {len(best)} procesos únicos  ({out})", file=sys.stderr)

if __name__ == "__main__":
    main()
