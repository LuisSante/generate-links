# Coleta de contratos (cartão de crédito) - TJBA via DataJud/CNJ

Pipeline em 3 etapas. Cada pasta tem seu script e seus JSONL de saída.

```
1_extract/  -> baixa do DataJud (bruto)
2_filtrar/  -> separa ativos x arquivados
3_dedup/    -> um registro por processo
```

## 1_extract - extração (DataJud API)
`gerar_links_datajud.py` consulta a API pública do DataJud e grava um JSONL
por sistema (Eproc / PJe), cartão de crédito (assuntos 7772, 9585).

```bash
cd 1_extract
python3 gerar_links_datajud.py --system Eproc --out eproc.jsonl
python3 gerar_links_datajud.py --system PJe   --out pje.jsonl
```
Saída: `eproc.jsonl` (193.593), `pje.jsonl` (70.467).

## 2_filtrar - ativos x arquivados
`filtrar_activos.py` reconsulta o DataJud em lotes e separa por movimento de
arquivamento (código 246).
```bash
cd 2_filtrar
python3 filtrar_activos.py ../1_extract/eproc.jsonl
python3 filtrar_activos.py ../1_extract/pje.jsonl
```
Saída: `*_activos.jsonl` + `*_arquivados.jsonl`.

> ATENÇÃO: o código 246 NÃO é 100% confiável. Os `movimentos` do DataJud vêm
> incompletos em processos antigos, então há arquivados que escapam para
> "ativos". A verdade sobre acessar um processo só se confirma abrindo no
> portal (etapa de acesso, com CAPTCHA). Use este filtro como PRIORIDADE,
> não como verdade absoluta.

## 3_dedup - deduplicação
`deduplicar.py` colapsa para um registro por `numero_processo` (mantém a 1ª
instância, onde está o contrato; une `assuntos` e lista `graus`).
```bash
cd 3_dedup
python3 deduplicar.py ../2_filtrar/eproc_activos.jsonl
python3 deduplicar.py ../2_filtrar/pje_activos.jsonl
```
Saída: `eproc_activos_dedup.jsonl` (13.433), `pje_activos_dedup.jsonl` (32.523).

## Números
| Etapa | Eproc | PJe |
|---|---|---|
| 1. bruto | 193.593 | 70.467 |
| 2. ativos | 16.762 | 36.376 |
| 3. ativos + únicos | 13.433 | 32.523 |

## Campos do JSONL
`numero_processo`, `numero_raw`, `tribunal`, `grau` (+ `graus` no dedup),
`sistema`, `nivel_sigilo`, `classe`, `assuntos`, `orgao_julgador`,
`data_ajuizamento`, `url_consulta`, `fonte`, `coletado_em` (+ `arquivado` na etapa 2).

APIKey pública do CNJ: https://datajud-wiki.cnj.jus.br/api-publica/acesso
