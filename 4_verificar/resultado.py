# Parse the response of POST /projudi/buscas/ProcessosParte.
#
# The captcha code is an INPUT to this flow -- supplied by the operator, one per
# search (PROJUDI invalidates it after a single use). Nothing here generates or
# reads a captcha; this module only classifies what comes back afterwards.
#
# Known server replies, verified against the TJBA protocol notes:
#   "Processo arquivado!"              -> case exists but is archived
#   "Caracteres da imagem inválidos"   -> wrong captcha code
#   "already validated captcha" (500)  -> code already spent, get a fresh one
#   "Selecione mais critérios de busca"-> number not searchable here (PJe `8…`)

import html as _html
import re
import unicodedata

# Verdicts, in priority order: the first matching pattern wins.
PATTERNS = [
    ("arquivado",     r"processo\s+arquivado"),
    ("captcha_usado", r"already\s+validated\s+captcha"),
    ("captcha_invalido", r"caracteres\s+da\s+imagem\s+invalidos"),
    ("criterios_insuficientes", r"selecione\s+mais\s+criterios\s+de\s+busca"),
    ("nao_encontrado", r"nenhum\s+(registro|processo)\s+encontrado"),
    ("sem_permissao", r"sigilo|acesso\s+negado|nao\s+autorizado"),
]

# The error box renders as "Verifique os seguintes erros:" followed by an <li>
# per message. Markup varies between PROJUDI screens, so match on the text.
ERRO_BLOCO = re.compile(r"verifique\s+os\s+seguintes\s+erros?\s*:?(.{0,2000})",
                        re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")
LI = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)


def normalizar(texto):
    """Lowercase, unescape entities, strip accents, collapse whitespace.

    The server mixes raw UTF-8 and HTML entities ("inv&aacute;lidos"), so both
    have to reduce to the same plain form before matching.
    """
    texto = _html.unescape(texto or "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).lower()


def mensagens_de_erro(html):
    """Extract the messages listed under 'Verifique os seguintes erros'."""
    bloco = ERRO_BLOCO.search(html or "")
    if not bloco:
        return []
    trecho = bloco.group(1)
    itens = [_html.unescape(TAG.sub("", m)).strip() for m in LI.findall(trecho)]
    itens = [re.sub(r"\s+", " ", i) for i in itens if i.strip()]
    if itens:
        return itens
    # Fallback: no <li> in this skin -- take the first non-empty text line.
    texto = _html.unescape(TAG.sub("\n", trecho))
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha:
            return [linha]
    return []


def classificar(html, status=200):
    """Return (veredicto, mensagens).

    veredicto is one of: arquivado | captcha_usado | captcha_invalido |
    criterios_insuficientes | nao_encontrado | sem_permissao | ok | desconhecido
    """
    plano = normalizar(html)
    msgs = mensagens_de_erro(html)

    for veredicto, patron in PATTERNS:
        if re.search(patron, plano):
            return veredicto, msgs

    if status >= 500:
        return "erro_servidor", msgs
    if msgs:
        return "desconhecido", msgs
    # No error block at all: the search returned a real result page.
    return "ok", []


def eh_ativo(veredicto):
    """True only when the case exists and is not archived."""
    return veredicto == "ok"
