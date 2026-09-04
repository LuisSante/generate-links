from pathlib import Path
from dotenv import load_dotenv
from scrapy.exceptions import CloseSpider

from paddleocr import PaddleOCR
import numpy as np
import scrapy
import json
import re
import cv2
import os

load_dotenv()

class LegalSpider(scrapy.Spider):
    name = os.getenv("name")
    allowed_domains = [os.getenv("allowed_domains")]
    start_urls = [os.getenv("legal_url")]
    max_retries = 3
    max_saved = 200
    html_dir = Path("html_group")
    saved = 0

    def __init__(self, limite=None, proceso=None, test=None, **kwargs):
        super().__init__(**kwargs)

        self.proceso = proceso

        if test:
            self.html_dir = self.html_dir / test

        if limite is not None:
            limite = str(limite).lower()

            self.max_saved = (
                0 if limite in ("todo", "todos", "all") else int(limite)
            )

    ocr = PaddleOCR(
        engine="paddle",
        device="gpu:0",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    def parse(self, response):
        main_src = response.xpath('//frame[@name="mainFrame"]/@src').get()
        yield response.follow(main_src, callback=self.parse_main)

    def parse_json(self, response):
        Path("main_page.html").write_bytes(response.body)

        form = response.css("form#formConsultaPublica")
        numero_input = form.css("input#numeroProcesso")

        yield {
            "form_action": response.urljoin(form.attrib["action"]),
            "form_method": form.attrib["method"],
            "input_name": numero_input.attrib["name"],
            "input_maxlength": numero_input.attrib["maxlength"],
            "legal_input": form.css("input#captcha").attrib["name"],
            "legal_img": response.urljoin(
                response.css("#idImg").attrib["src"]
            ),
        }

    def read_json(self, response):
        if self.proceso:
            return [self.proceso]

        list_process = []
        with open("../3_dedup/eproc_activos_dedup.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                numero_processo = json.loads(line)["numero_processo"]
                list_process.append(numero_processo)

        return list_process

    def parse_main(self, response):
        form = response.css("form#formConsultaPublica")
        numero_input = form.css("input#numeroProcesso")

        legal_img = response.urljoin(
            response.css("#idImg").attrib["src"]
        )

        form_action = response.urljoin(form.attrib["action"])
        process_list = self.read_json(response)

        for i in range(len(process_list)):
            yield self.search_request(
                process_number=process_list[i],
                iteration=i + 1,
                attempt=0,
                main_url=response.url,
                legal_img=legal_img,
                form_action=form_action,
            )

    def search_request(
        self, process_number, iteration, attempt, main_url, legal_img, form_action
    ):
        return scrapy.Request(
            main_url,
            callback=self.open_session,
            priority=30 if attempt else 0,
            meta={
                "cookiejar": f"{iteration}-{attempt}",
                "main_url": main_url,
                "legal_img": legal_img,
                "form_action": form_action,
                "process_number": process_number,
                "iteration": iteration,
                "attempt": attempt,
            },
            dont_filter=True,
        )

    def open_session(self, response):
        yield scrapy.Request(
            response.meta["legal_img"],
            callback=self.parse_legal_image,
            priority=40,
            meta=response.meta,
            dont_filter=True,
        )

    def parse_legal_image(self, response):
        iteration = response.meta["iteration"]
        process_number = response.meta["process_number"]
        form_action = response.meta["form_action"]

        image = cv2.imdecode(
            np.frombuffer(response.body, np.uint8), cv2.IMREAD_COLOR
        )
        result = self.ocr.predict(image)

        text = ""

        for res in result:
            texts = res["rec_texts"]

            if texts:
                text = "".join(texts)

        text = "".join(text.split())

        print()
        print("=" * 60)
        print(f"iteration: {iteration}")
        print(f"extract_text_to_image: {text}")
        print(f"process_number: {process_number}")
        print(f"form_action: {form_action}")
        print("=" * 60)

        yield scrapy.FormRequest(
            url=form_action,
            method="POST",
            priority=50,
            formdata={
                "numeroProcesso": process_number,
                "nome": "",
                "captcha": text,
            },
            callback=self.result,
            meta={
                **response.meta,
                "handle_httpstatus_all": True,
                "captcha": text,
            },
            dont_filter=True,
        )

    def read_download(self, response):
        href = response.css(
            'a[href^="javascript:chamaDownloadProcesso"]::attr(href)'
        ).get()

        if not href:
            return None

        match = re.search(r"\((\d+)\)", href)

        if not match:
            return None

        return {
            "cod_processo": match.group(1),
            "url": response.urljoin(
                f"/projudi/acoes/DownloadProcesso?numeroProcesso={match.group(1)}"
            ),
        }

    def read_arquivos(self, response):
        bloqueados = response.text.count(
            "cadastrados no sistema podem acess"
        )
        livres = len(
            response.css('a[href*="DownloadArquivo?arquivo="]')
        )

        return {"bloqueados": bloqueados, "livres": livres}

    def read_cod(self, response):
        href = response.css(
            'a[href*="listagens/DadosProcesso"]::attr(href)'
        ).get()

        if not href:
            return None

        match = re.search(r"numeroProcesso=(\d+)", href)

        return match.group(1) if match else None

    def read_messages(self, response):
        messages = []

        for box in response.css(".erro, .aviso, .info, .sucesso"):
            kind = box.attrib.get("class", "").strip()

            items = [t.strip() for t in box.css("li::text").getall() if t.strip()]

            if not items:
                items = [
                    t.strip()
                    for t in box.xpath(
                        ".//text()[not(ancestor::strong or ancestor::b"
                        " or ancestor::legend)]"
                    ).getall()
                    if t.strip()
                ]

            for item in items:
                messages.append({"tipo": kind, "texto": item})

        return messages

    def classify(self, response, messages):
        if response.status != 200:
            return f"http_{response.status}"

        if "SessionExpired" in response.text:
            return "sesion_expirada"

        if "DADOS DO PROCESSO" in response.text:
            return "dados_processo"

        if messages:
            return messages[0]["tipo"]

        return "desconhecido"

    retry_marks = ("imagem", "captcha", "caracteres")

    def should_retry(self, kind, messages):
        if kind in ("http_500", "sesion_expirada"):
            return True

        for message in messages:
            texto = message["texto"].lower()

            if any(mark in texto for mark in self.retry_marks):
                return True

        return False

    def save_html(self, response, kind):
        path = self.html_dir / kind / f"{response.meta['process_number']}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.body)

        self.saved += 1

        return path

    def discard(self, response, kind, messages, motivo):
        record = {
            "process_number": response.meta["process_number"],
            "iteration": response.meta["iteration"],
            "attempt": response.meta["attempt"],
            "status": response.status,
            "tipo": kind,
            "motivo": motivo,
            "mensagens": messages,
        }

        with open("descartados.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def result(self, response):
        response = response.replace(encoding="iso-8859-1")

        process_number = response.meta["process_number"]
        iteration = response.meta["iteration"]
        attempt = response.meta["attempt"]
        captcha = response.meta["captcha"]

        messages = self.read_messages(response)
        kind = self.classify(response, messages)

        if self.should_retry(kind, messages) and attempt + 1 < self.max_retries:
            print(f"[{iteration}] {process_number} {kind} -> reintento {attempt + 1}")

            yield self.search_request(
                process_number=process_number,
                iteration=iteration,
                attempt=attempt + 1,
                main_url=response.meta["main_url"],
                legal_img=response.meta["legal_img"],
                form_action=response.meta["form_action"],
            )
            return

        download = self.read_download(response)
        arquivos = self.read_arquivos(response)
        cod = self.read_cod(response)

        if (
            kind == "dados_processo"
            and not download
            and cod
            and not response.meta.get("detalle")
        ):
            print(f"[{iteration}] {process_number} -> DadosProcesso({cod})")

            yield scrapy.Request(
                response.urljoin(
                    f"/projudi/listagens/DadosProcesso?numeroProcesso={cod}"
                ),
                callback=self.result,
                priority=60,
                meta={**response.meta, "detalle": True},
                dont_filter=True,
            )
            return

        grupo = kind

        if kind == "dados_processo" and not arquivos["bloqueados"]:
            grupo = "sem_login"

        html = self.save_html(response, grupo)

        print()
        print("=" * 60)
        print(f"RESULTADO {self.saved}/{self.max_saved or 'todos'}")
        print(f"iteration: {iteration}")
        print(f"process_number: {process_number}")
        print(f"captcha: {captcha}")
        print(f"status: {response.status}")
        print(f"tipo: {kind}")
        print(f"download: {download['url'] if download else 'NO'}")
        print(f"arquivos: {arquivos['livres']} livres / {arquivos['bloqueados']} bloqueados")
        for message in messages:
            print(f"  [{message['tipo']}] {message['texto']}")
        print(f"html: {html}")
        print("=" * 60)

        if kind == "dados_processo":
            yield {
                "process_number": process_number,
                "iteration": iteration,
                "url": response.url,
                "html": str(html),
                "mensagens": messages,
                "cod_processo": cod,
                "grupo": grupo,
                "arquivos": arquivos,
                "download": download,
            }
        else:
            self.discard(response, kind, messages, kind)

        if self.max_saved and self.saved >= self.max_saved:
            raise CloseSpider(f"limite de {self.max_saved} html alcanzado")
