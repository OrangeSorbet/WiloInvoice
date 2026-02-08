import os
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PDF_PATH = os.path.join(BASE_DIR, "invoice.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler-25.11.0\Library\bin"

DPI = 300

OCR_CONFIGS = [
    "--oem 1 --psm 3",
    "--oem 1 --psm 4",
    "--oem 1 --psm 6",
    "--oem 1 --psm 11",
    "--oem 1 --psm 12",

    "--oem 3 --psm 3",
    "--oem 3 --psm 4",
    "--oem 3 --psm 6",
    "--oem 3 --psm 11",
    "--oem 3 --psm 12",

    "--oem 1 --psm 6 -l eng+osd",

    "--oem 1 --psm 13",

    "--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789.,"
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------- Load PDF --------
pages = convert_from_path(
    PDF_PATH,
    dpi=DPI,
    poppler_path=POPPLER_PATH,
    use_pdftocairo=True
)

print(f"Loaded {len(pages)} page(s)")

for page_no, page in enumerate(pages, start=1):
    img = np.array(page)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 2
    )

    for cfg in OCR_CONFIGS:
        safe_name = (
            cfg.replace("--", "")
               .replace(" ", "_")
               .replace("+", "_")
               .replace("=", "")
               .replace(",", "")
        )

        print(f"Page {page_no} | {cfg}")

        try:
            text = pytesseract.image_to_string(
                gray,
                config=cfg
            )

            filename = f"page_{page_no}_{safe_name}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

        except pytesseract.TesseractError as e:
            print(f"Skipped config [{cfg}]: {e}")

print("OCR mode comparison completed.")
