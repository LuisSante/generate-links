from pathlib import Path
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

import pytesseract
import scrapy
import os

load_dotenv()

class LegalSpider(scrapy.Spider):
    name = os.getenv("name")
    allowed_domains = [os.getenv("allowed_domains")]
    start_urls = [os.getenv("legal_url")]

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

    def parse_main(self, response):
        form = response.css("form#formConsultaPublica")
        numero_input = form.css("input#numeroProcesso")

        legal_img = response.urljoin(
            response.css("#idImg").attrib["src"]
        )

        yield scrapy.Request(
            legal_img,
            callback=self.parse_captcha,
            meta={
                "legal_img": legal_img,
                "form_action": response.urljoin(form.attrib["action"]),
                "input_name": numero_input.attrib["name"],
            },
        )

    def parse_captcha(self, response):
        image = Image.open(BytesIO(response.body))

        # text = pytesseract.image_to_string(image, config="--psm 8")
        # text = pytesseract.image_to_string(image, config="--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789")
        # text = pytesseract.image_to_string(image, config="--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        # text = pytesseract.image_to_string(image, config="--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
        text = pytesseract.image_to_string(image)

        yield {
            "legal_img": response.meta["legal_img"],
            "captcha_text": text.strip(),
        }