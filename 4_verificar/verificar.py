# Step 4 - Assisted verification against the PROJUDI public consultation.
#
# PROJUDI issues ONE single-use captcha per search. This tool does everything
# around that: opens the session, downloads the captcha image to a fixed path,
# waits for the operator to type the code, submits the search, classifies the
# reply and appends it to JSONL. Reading the image is the operator's job --
# nothing here inspects or solves it.
#
# Scope: calibrating the DataJud classifier on a SAMPLE (~100 cases). At one
# captcha per case this is not a bulk-validation tool and cannot become one;
# for the full set the answer is DataJud (step 2) or institutional access.
#
# Usage:
#   # draw a stratified sample from the classified output
#   python3 verificar.py --muestrear ../2_filtrar/eproc_arquivados.jsonl -n 100 --out muestra.jsonl
#
#   # verify it, one captcha at a time
#   python3 verificar.py muestra.jsonl --out verificados.jsonl

import argparse, json, os, random, sys, time
from collections import defaultdict

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resultado import classificar

BASE = "https://projudi.tjba.jus.br/projudi"
UA = ("PesquisaAcademicaFGV/1.0 (verificacao de situacao processual; "
      "contato: estrada86@gmail.com)")


# ------------------------------------------------------------------ sampling

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def muestrear(path, n, out, seed=42):
    """Stratified sample by `estado_motivo` family, so every bucket is covered."""
    estratos = defaultdict(list)
    for r in load_jsonl(path):
        motivo = r.get("estado_motivo", "")
        if "mérito decidido" in motivo:
            key = "merito"
        elif "sin movimiento" in motivo:
            key = "inactivo"
        elif "códigos de cierre" in motivo:
            key = "cerrado"
        else:
            key = r.get("estado", "otro")
        estratos[key].append(r)

    rng = random.Random(seed)
    por_estrato = max(1, n // max(1, len(estratos)))
    muestra = []
    for key, rows in sorted(estratos.items()):
        k = min(por_estrato, len(rows))
        muestra.extend(rng.sample(rows, k))
        print(f"  {key:<10} {len(rows):>7} disponibles -> {k} muestreados",
              file=sys.stderr)
    rng.shuffle(muestra)
    with open(out, "w", encoding="utf-8") as f:
        for r in muestra[:n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n{min(len(muestra), n)} casos -> {out}", file=sys.stderr)



# --------------------------------------------------------------- terminal UI

def pintar_captcha(path, ancho=76):
    """Render the captcha as ANSI half-blocks so it can be read in the terminal.

    Two pixel rows per text row via the upper-half block: foreground paints the
    top pixel, background the bottom one. Returns None if Pillow is missing, so
    the caller can fall back to "open the file yourself".
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    img = Image.open(path).convert("RGB")
    w, h = img.size
    alto = max(2, round(h * ancho / w))
    alto += alto % 2                     # even: two pixel rows per text row
    img = img.resize((ancho, alto))
    px = img.load()
    filas = []
    for y in range(0, alto, 2):
        fila = []
        for x in range(ancho):
            tr, tg, tb = px[x, y]
            br, bg, bb = px[x, y + 1]
            fila.append(f"\x1b[38;2;{tr};{tg};{tb}m\x1b[48;2;{br};{bg};{bb}m\u2580")
        filas.append("".join(fila) + "\x1b[0m")
    return "\n".join(filas)


def pedir_codigo(session, img_path, etiqueta):
    """Fetch a fresh captcha, show it, and return the code typed by the operator."""
    bajar_captcha(session, img_path)
    arte = pintar_captcha(img_path)
    if arte:
        print("\n" + arte, file=sys.stderr)
    else:
        print(f"\n  (instala Pillow para verlo aquí; imagen en {img_path})",
              file=sys.stderr)
    return input(f"{etiqueta}\n  código del captcha: ").strip()


def consultar_uno(numero, img_path, reintentos):
    """Verify a single case number interactively. Returns the verdict."""
    sesion = abrir_sesion()
    for intento in range(1, reintentos + 1):
        codigo = pedir_codigo(sesion, img_path, f"  proceso: {numero}")
        if not codigo:
            return "saltado", [], None
        veredicto, mensajes, status = consultar(sesion, numero, codigo)
        if veredicto in ("captcha_invalido", "captcha_usado"):
            print(f"  {veredicto} -- captcha nuevo (intento {intento}/{reintentos})",
                  file=sys.stderr)
            continue
        return veredicto, mensajes, status
    return "fallo_captcha", [], None


def imprimir_veredicto(numero, veredicto, mensajes):
    activo = "True" if eh_activo(veredicto) else "False"
    print(f"\n{'caso':<30} {'veredicto':<26} activo")
    print(f"{numero:<30} {veredicto:<26} {activo}")
    if mensajes:
        print(f"{'':<30} mensajes: {mensajes}")


def eh_activo(veredicto):
    return veredicto == "ok"


# ------------------------------------------------------------------- session

def abrir_sesion():
    """GET PaginaPrincipal.jsp to obtain a JSESSIONID; / is only a frameset."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    s.get(f"{BASE}/PaginaPrincipal.jsp", timeout=30).raise_for_status()
    return s


def bajar_captcha(session, path):
    """Save the captcha image so the operator can read it. One code per search."""
    r = session.get(f"{BASE}/captcha.jpg", timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    return path


def consultar(session, numero, codigo):
    """Submit one search with an operator-supplied captcha code."""
    r = session.post(f"{BASE}/buscas/ProcessosParte",
                     data={"numeroProcesso": numero, "nome": "", "captcha": codigo},
                     timeout=60)
    veredicto, mensajes = classificar(r.text, r.status_code)
    return veredicto, mensajes, r.status_code


# --------------------------------------------------------------- interactive

def ya_hechos(path):
    if not os.path.exists(path):
        return set()
    return {r["numero_processo"] for r in load_jsonl(path)}


def verificar_lote(entrada, salida, img_path, delay, reintentos):
    registros = list(load_jsonl(entrada))
    hechos = ya_hechos(salida)
    pendientes = [r for r in registros
                  if r.get("numero_processo") not in hechos]
    print(f"{len(registros)} en la muestra | {len(hechos)} ya verificados | "
          f"{len(pendientes)} pendientes\n", file=sys.stderr)
    if not pendientes:
        return

    print("El captcha se dibuja en la terminal en cada consulta.\n"
          "ENTER salta el caso, 'q' termina (puedes retomar después: el "
          "avance se guarda).\n", file=sys.stderr)

    sesion = abrir_sesion()
    hechos_ahora = 0
    with open(salida, "a", encoding="utf-8") as out:
        for i, rec in enumerate(pendientes, 1):
            numero = rec["numero_processo"]
            veredicto = None
            for intento in range(1, reintentos + 1):
                try:
                    bajar_captcha(sesion, img_path)
                except Exception as e:
                    print(f"  [error bajando captcha: {e}]", file=sys.stderr)
                    sesion = abrir_sesion()
                    continue
                try:
                    arte = pintar_captcha(img_path)
                    if arte:
                        print("\n" + arte, file=sys.stderr)
                    codigo = input(f"[{i}/{len(pendientes)}] {numero}\n"
                                   f"  código del captcha: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\ninterrumpido", file=sys.stderr)
                    return
                if codigo.lower() == "q":
                    print(f"\n{hechos_ahora} verificados en esta sesión",
                          file=sys.stderr)
                    return
                if not codigo:
                    veredicto, mensajes, status = "saltado", [], None
                    break
                try:
                    veredicto, mensajes, status = consultar(sesion, numero, codigo)
                except Exception as e:
                    print(f"  [error en la consulta: {e}]", file=sys.stderr)
                    continue
                if veredicto in ("captcha_invalido", "captcha_usado"):
                    print(f"  {veredicto} -- captcha nuevo "
                          f"(intento {intento}/{reintentos})", file=sys.stderr)
                    veredicto = None
                    continue
                break

            if veredicto is None:
                veredicto, mensajes, status = "fallo_captcha", [], None

            rec["projudi_veredicto"] = veredicto
            rec["projudi_mensajes"] = mensajes
            rec["projudi_status"] = status
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            hechos_ahora += 1
            print(f"  -> {veredicto} {mensajes if mensajes else ''}\n",
                  file=sys.stderr)
            time.sleep(delay)
    print(f"{hechos_ahora} verificados -> {salida}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", help="JSONL con la muestra a verificar")
    ap.add_argument("--muestrear", metavar="JSONL",
                    help="extraer una muestra estratificada y salir")
    ap.add_argument("-n", type=int, default=100, help="tamaño de la muestra")
    ap.add_argument("--out", default="verificados.jsonl")
    ap.add_argument("--img", default="captcha_atual.jpg")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--reintentos", type=int, default=3)
    ap.add_argument("--numero", help="verificar un solo proceso y salir")
    a = ap.parse_args()

    if a.numero:
        veredicto, mensajes, _ = consultar_uno(a.numero, a.img, a.reintentos)
        imprimir_veredicto(a.numero, veredicto, mensajes)
        return
    if a.muestrear:
        muestrear(a.muestrear, a.n, a.out)
        return
    if not a.input:
        ap.error("falta el JSONL de entrada (o usa --muestrear)")
    verificar_lote(a.input, a.out, a.img, a.delay, a.reintentos)


if __name__ == "__main__":
    main()
