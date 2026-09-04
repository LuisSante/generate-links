# TJBA credit-card contracts — DataJud/CNJ

3-step pipeline. Each folder holds its script and its JSONL outputs.

```
1_extract/  -> raw download from the DataJud API (Eproc / PJe, subjects 7772, 9585)
2_filtrar/  -> split active vs archived (movement code 246)
3_dedup/    -> one record per case number (keeps 1st instance)
```

## Run

```bash
cd 1_extract
python3 gerar_links_datajud.py --system Eproc --out eproc.jsonl
python3 gerar_links_datajud.py --system PJe   --out pje.jsonl
```

```bash
cd 2_filtrar
python3 filtrar_activos.py ../1_extract/eproc.jsonl
python3 filtrar_activos.py ../1_extract/pje.jsonl
```

```bash
cd 3_dedup
python3 deduplicar.py ../2_filtrar/eproc_activos.jsonl
python3 deduplicar.py ../2_filtrar/pje_activos.jsonl
```

> Movement code 246 is not 100% reliable (old cases have incomplete
> `movimentos`). Use the active/archived split as a priority hint, not truth.

## Numbers

| Step             | Eproc   | PJe    |
|------------------|---------|--------|
| 1. raw           | 193,593 | 70,467 |
| 2. active        | 16,762  | 36,376 |
| 3. active unique | 13,433  | 32,523 |

## Environment

Managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`); Scrapy project in `spider_links/`.
Setup commands: [docs/setup.md](docs/setup.md).

Public CNJ API key: https://datajud-wiki.cnj.jus.br/api-publica/acesso
