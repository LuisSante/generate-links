from pathlib import Path
from PIL import Image
from io import BytesIO
import pytesseract

import scrapy


class ProjudiSpider(scrapy.Spider):
    name = "projudi"
    allowed_domains = ["projudi.tjba.jus.br"]
    start_urls = ["https://projudi.tjba.jus.br/projudi/"]

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
            "captcha_input": form.css("input#captcha").attrib["name"],
            "captcha_img": response.urljoin(
                response.css("#idImg").attrib["src"]
            ),
        }

    def parse_main(self, response):
        form = response.css("form#formConsultaPublica")
        numero_input = form.css("input#numeroProcesso")

        bck_img = response.urljoin(
            response.css("#idImg").attrib["src"]
        )

        yield scrapy.Request(
            bck_img,
            callback=self.parse_captcha,
            meta={
                "bck_img": bck_img,
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
            "bck_img": response.meta["bck_img"],
            "captcha_text": text.strip(),
        }