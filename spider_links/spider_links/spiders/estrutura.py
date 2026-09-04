from pathlib import Path
from dotenv import load_dotenv

import scrapy
import os

load_dotenv()


class EstruturaSpider(scrapy.Spider):
    name = "estrutura"
    allowed_domains = [os.getenv("allowed_domains")]
    start_urls = [os.getenv("legal_url")]

    def parse(self, response):
        # The root URL is only a frameset; the form lives in mainFrame.
        main_src = response.xpath('//frame[@name="mainFrame"]/@src').get()
        yield response.follow(main_src, callback=self.parse_main)

    def parse_main(self, response):
        Path("main_page.html").write_bytes(response.body)

        form = response.css("form#formConsultaPublica")
        numero_input = form.css("input#numeroProcesso")

        yield {
            "form_action": response.urljoin(form.attrib["action"]),
            "form_method": form.attrib["method"],
            "input_name": numero_input.attrib["name"],
            "input_maxlength": numero_input.attrib["maxlength"],
            "captcha_input": form.css("input#captcha").attrib["name"],
            "captcha_img": response.urljoin(response.css("#idImg").attrib["src"]),
        }
