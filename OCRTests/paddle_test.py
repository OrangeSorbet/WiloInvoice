"""
Exhaustive PaddleOCR Testing Script (CPU/GPU safe + debug)
"""

import os
import cv2
import numpy as np
import itertools
import re
import warnings
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE_DIR, r"C:\Users\ashvi\Documents\VS_Codes\Python\WiloInvoice\DEBUG_PAGE.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "paddleresults")
BEST_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "best")
POPPLER_PATH = r"C:\poppler-25.12.0\Library\bin"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(BEST_OUTPUT_DIR, exist_ok=True)

# ================= FACTORS =================
preprocessing_methods = ['original', 'grayscale', 'adaptive_threshold', 'gaussian_blur', 
                         'bilateral_filter', 'clahe', 'median_blur', 'sharpen']
dpi_options = [200, 300, 400]
textline_options = [True, False]
text_det_thresh_options = [0.3, 0.5, 0.7]
box_thresh_options = [0.3, 0.5, 0.7]

# Maximum size for CPU images (prevent oneDNN errors)
CPU_MAX_SIDE = 2000

# ================= FUNCTIONS =================

def preprocess_variants(img):
    """Return dict of preprocessed images in RGB for PaddleOCR."""
    variants = {}
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    variants["original"] = img
    variants["grayscale"] = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    adapt = cv2.adaptiveThreshold(gray, 255,
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 31, 2)
    variants["adaptive_threshold"] = cv2.cvtColor(adapt, cv2.COLOR_GRAY2RGB)
    gblur = cv2.GaussianBlur(gray, (5,5), 0)
    variants["gaussian_blur"] = cv2.cvtColor(gblur, cv2.COLOR_GRAY2RGB)
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    variants["bilateral_filter"] = cv2.cvtColor(bilateral, cv2.COLOR_GRAY2RGB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray)
    variants["clahe"] = cv2.cvtColor(clahe, cv2.COLOR_GRAY2RGB)
    median = cv2.medianBlur(gray, 3)
    variants["median_blur"] = cv2.cvtColor(median, cv2.COLOR_GRAY2RGB)
    kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
    sharp = cv2.filter2D(gray, -1, kernel)
    variants["sharpen"] = cv2.cvtColor(sharp, cv2.COLOR_GRAY2RGB)

    return variants

def resize_image_for_ocr(img, max_side):
    """Resize image so width and height <= max_side while keeping aspect ratio."""
    h, w = img.shape[:2]
    scale = min(max_side / h, max_side / w, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"Resized image from ({w},{h}) to ({new_w},{new_h})")
    return img

# ================= PROCESS PDF =================

device_type = "gpu" if cv2.cuda.getCudaEnabledDeviceCount() > 0 else "cpu"
print(f"Using device: {device_type.upper()}")

for dpi in dpi_options:
    pages = convert_from_path(
        PDF_PATH, dpi=dpi, poppler_path=POPPLER_PATH, use_pdftocairo=True
    )
    print(f"Loaded {len(pages)} page(s) @ {dpi} DPI")

    for page_no, page in enumerate(pages, start=1):
        print(f"\nProcessing Page #{page_no} @ {dpi} DPI")
        img = np.array(page)
        variants = preprocess_variants(img)

        for textline, t_det, b_det in itertools.product(
            textline_options, text_det_thresh_options, box_thresh_options
        ):

            ocr = PaddleOCR(device=device_type, use_textline_orientation=textline, lang="en")

            for prep_name, prep_img in variants.items():
                # Resize only on CPU
                if device_type == "cpu":
                    prep_img = resize_image_for_ocr(prep_img, max_side=CPU_MAX_SIDE)

                combo = (
                    f"page{page_no}_dpi{dpi}_textline{int(textline)}"
                    f"_td{t_det}_bt{b_det}_prep{prep_name}"
                )
                print(f"\nRunning OCR: {combo}")

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        result = ocr.predict(
                            input=prep_img,
                            text_det_thresh=t_det,
                            text_det_box_thresh=b_det
                        )
                    except Exception as e:
                        print(f"❌ OCR failed for {combo}: {e}")
                        continue  # skip this combo

                lines = [seg.text for res in result for seg in res]
                text_out = "\n".join(lines)

                # Skip empty outputs
                if not text_out.strip():
                    print(f"⚠️ Skipping empty OCR result for {combo}")
                    continue

                path = os.path.join(OUTPUT_DIR, combo + ".txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text_out)
                print(f"Saved OCR result: {path} ({len(text_out)} chars)")

# ================= BEST RESULT SELECTION =================

valid_pattern = re.compile(r"[a-zA-Z0-9\s.,%$-]")
all_txt = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt")]

pages_dict = {}
for f in all_txt:
    m = re.match(r"page(\d+)_", f)
    if m:
        p = int(m.group(1))
        pages_dict.setdefault(p, []).append(f)

for p, files in pages_dict.items():
    best_score = -1
    best_txt = ""
    best_file = ""
    for fn in files:
        fp = os.path.join(OUTPUT_DIR, fn)
        txt = open(fp, encoding="utf-8").read()
        wcount = len(txt.split())
        vchars = len(valid_pattern.findall(txt))
        garbage = len(txt) - vchars
        score = wcount + vchars - garbage

        if score > best_score:
            best_score = score
            best_txt = txt
            best_file = fn

    out = os.path.join(BEST_OUTPUT_DIR, f"page_{p}_best.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(best_txt)
    print(f"\nPage {p} → Best file: {best_file} (score {best_score})")
    print(f"Saved best result: {out} ({len(best_txt)} chars)")

print("\n✅ All done!")
