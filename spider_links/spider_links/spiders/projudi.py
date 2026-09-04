from pathlib import Path
from dotenv import load_dotenv

from paddleocr import PaddleOCR
import scrapy
import json
import os

load_dotenv()

class LegalSpider(scrapy.Spider):
    name = os.getenv("name")
    allowed_domains = [os.getenv("allowed_domains")]
    start_urls = [os.getenv("legal_url")]

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

        process_list = self.read_json(response)

        for i in range(len(process_list)):
            yield scrapy.Request(
                legal_img,
                callback=self.parse_legal_image,
                meta={
                    "legal_img": legal_img,
                    "process_number": process_list[i],
                    "form_action": response.urljoin(form.attrib["action"]),
                    "input_name": numero_input.attrib["name"],
                    "iteration": i + 1,
                },
                dont_filter=True,
            )

    def parse_legal_image(self, response):
        image_url = os.getenv("complete_legal_url")
        iteration = response.meta["iteration"]
        result = self.ocr.predict(image_url)

        text = ""

        for res in result:
            texts = res["rec_texts"]

            if texts:
                text = "".join(texts)

        text = "".join(text.split())

        print()
        print("=" * 60)
        yield {
            "iteration": iteration,
            "legal_img": response.meta["legal_img"],
            "extract_text_to_image": text,
            "process_number": response.meta["process_number"],
            "form_action": response.meta["form_action"],
            "input_name": response.meta["input_name"],
        }

        print("=" * 60)