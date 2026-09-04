from paddleocr import PaddleOCR

ocr = PaddleOCR(
    engine="paddle",
    device="gpu:0",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

for res in ocr.predict("captcha.jpg"):
    print("\n".join(res["rec_texts"]))