# DataJud/CNJ - Commands (credit card cases)

Source: DataJud/CNJ public API. Filters cases by subject and returns the CNJ case
number plus metadata. Official docs and public key:
https://datajud-wiki.cnj.jus.br/api-publica/acesso

The APIKey below is public (published by CNJ, read-only). It is the same for every
court - only the `api_publica_<court>` part of the endpoint changes. If it ever
returns 401, copy the new key from the wiki above.

---

## Commands

### Show 3 credit card cases (subject 7772)

```bash
curl -s -X POST 'https://api-publica.datajud.cnj.jus.br/api_publica_tjba/_search' \
  -H 'Authorization: APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==' \
  -H 'Content-Type: application/json' \
  --data '{"size":3,"query":{"term":{"assuntos.codigo":7772}}}' | python3 -m json.tool
```

### Show 1 full case (all fields)

```bash
curl -s -X POST 'https://api-publica.datajud.cnj.jus.br/api_publica_tjba/_search' \
  -H 'Authorization: APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==' \
  -H 'Content-Type: application/json' \
  --data '{"size":1,"query":{"term":{"assuntos.codigo":7772}}}' | python3 -m json.tool
```

### Count how many exist (total only, no download)

```bash
curl -s -X POST 'https://api-publica.datajud.cnj.jus.br/api_publica_tjba/_search' \
  -H 'Authorization: APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==' \
  -H 'Content-Type: application/json' \
  --data '{"size":0,"track_total_hits":true,"query":{"term":{"assuntos.codigo":7772}}}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['hits']['total']['value'])"
```

---

## Generate links

```bash
python3 gerar_links_datajud.py --court tjba --subjects 7772 --max 50000 --out links_cartao.json
```

### Flags

| Flag | What it does | Default |
|---|---|---|
| `--court` | Court (`tjba`, `tjsp`, `tjrj`, `stj`, ...) | `tjba` |
| `--subjects` | CNJ subject codes (accepts several) | `7772 9585 11806` |
| `--max` | How many cases to collect | `2000` |
| `--page` | API page size | `200` |
| `--delay` | Pause between pages (seconds) | `0.5` |
| `--out` | Output file | `links.json` |

---

## Subject codes (TJBA)

| Code | Subject | Cases (TJBA) |
|---|---|---|
| `7772`  | Credit Card | ~239,600 |
| `9585`  | Credit Card (variant) | ~28,400 |
| `11806` | Payroll loan (RMC / payroll credit card) | ~453,900 |

- Credit card only: `--subjects 7772` (or `7772 9585`)
- Include payroll/RMC: `--subjects 7772 9585 11806`

---

## Output

List of objects. Keys are in Portuguese:

```json
{
  "numero_processo": "0167541-35.2026.8.05.0001",
  "numero_raw": "01675413520268050001",
  "tribunal": "TJBA",
  "grau": "JE",
  "classe": "Procedimento do Juizado Especial Cível",
  "assuntos": ["Cartão de Crédito"],
  "orgao_julgador": "20ª VSJE DO CONSUMIDOR",
  "data_ajuizamento": "20260731...",
  "url_consulta": "...",
  "fonte": "datajud",
  "coletado_em": "2026-08-25"
}
```

Note: DataJud returns the case number and metadata, not the contract itself. To open
the case files, each case is consulted on the portal where it lives (in TJBA, credit
card cases are in Eproc ~80% and PJe ~20%, not Projudi), and the public consultation
requires a CAPTCHA per case.
