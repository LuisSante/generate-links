from pathlib import Path

import scrapy


class ProjudiSpider(scrapy.Spider):
    name = "projudi"
    allowed_domains = ["projudi.tjba.jus.br"]
    start_urls = ["https://projudi.tjba.jus.br/projudi/"]

    def parse(self, response):
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
            "captcha_img": response.urljoin(
                response.css("#idImg").attrib["src"]
            ),
        }
