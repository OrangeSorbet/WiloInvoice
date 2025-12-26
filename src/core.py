import re
import pdfplumber
import pytesseract
import cv2
import numpy as np
import spacy
from pdf2image import convert_from_path

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler-25.12.0\Library\bin"

AMOUNT_REGEX = r'(?:INR\s*)?(\d{1,3}(?:,\d{3})*\.\d{2})'


class InvoicePipeline:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            self.nlp = None

    def process_invoice(self, file_path):
        content = self._extract_content(file_path)
        text = content['text']

        if not text:
            return {"status": "Error", "error": "Empty File"}

        text = text.replace("₹", "INR ")
        text = text.replace("Rs.", "INR ")
        text = text.replace("Rs", "INR ")
        text = text.replace("â‚¹", "INR ")

        data = self._parse_deep_fields(text)
        return data

    def _extract_content(self, path):
        full_text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    full_text += text + "\n"

        if len(full_text) < 50:
            try:
                images = convert_from_path(path, poppler_path=POPPLER_PATH)
                for img in images:
                    cv_img = np.array(img)
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
                    _, thresh = cv2.threshold(
                        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                    )
                    full_text += pytesseract.image_to_string(thresh) + "\n"
            except:
                pass

        return {"text": full_text}

    def _parse_deep_fields(self, text):
        data = {
            "invoice_number": "N/A",
            "invoice_date": "N/A",
            "vendor_name": "Unknown",
            "vendor_gstin": "N/A",
            "buyer_name": "Unknown",
            "cgst": "0.00",
            "sgst": "0.00",
            "grand_total": "0.00",
            "currency": "INR"
        }

        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # -------- 1. Vendor --------
        for i, line in enumerate(lines[:10]):
            clean = line.upper().replace(" ", "")
            if "TAXINVOICE" in clean or "ORIGINAL" in clean:
                continue
            data['vendor_name'] = line
            break

        gst_pattern = r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}'
        all_gst = re.findall(gst_pattern, text)
        if all_gst:
            data['vendor_gstin'] = all_gst[0]

        # -------- 2. Buyer --------
        buyer_match = re.search(
            r'(?i)(invoice to|bill to|billed to)\s*[:.-]?\s*\n+([^\n]+)',
            text
        )
        if buyer_match:
            data['buyer_name'] = buyer_match.group(2).strip()

        # -------- 3. Invoice Meta --------
        inv_match = re.search(
            r'(?i)(invoice\s*no|inv\s*#)\s*[:.]?\s*([A-Za-z0-9/-]+)',
            text
        )
        if inv_match:
            data['invoice_number'] = inv_match.group(2)

        date_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', text)
        if date_match:
            data['invoice_date'] = date_match.group(1)

        # -------- 4. Amount Extraction 
        def extract_amount_smart(label_keywords):
            for i, line in enumerate(lines):
                if not any(k.lower() in line.lower() for k in label_keywords):
                    continue

                if "%" in line and not re.search(r'\.\d{2}', line):
                    continue

                matches = re.findall(AMOUNT_REGEX, line)
                if matches:
                    return matches[-1].replace(",", "")

                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if "%" in next_line:
                        continue
                    matches = re.findall(AMOUNT_REGEX, next_line)
                    if matches:
                        return matches[-1].replace(",", "")
            return None

        # -------- Taxes --------
        cgst = extract_amount_smart(["CGST"])
        if cgst:
            data['cgst'] = cgst

        sgst = extract_amount_smart(["SGST"])
        if sgst:
            data['sgst'] = sgst

        
        for key in ["Grand Total", "TOTAL AMOUNT", "Amount Payable", "Invoice Total"]:
            val = extract_amount_smart([key])
            if val:
                data['grand_total'] = val
                break

        if data['grand_total'] == "0.00":
            try:
                subtotal = extract_amount_smart(["Subtotal", "Sub Total", "Total"])
                subtotal = float(subtotal) if subtotal else 0

                cgst_val = float(data['cgst']) if data['cgst'] else 0
                sgst_val = float(data['sgst']) if data['sgst'] else 0

                computed = subtotal + cgst_val + sgst_val
                if computed > 0:
                    data['grand_total'] = f"{computed:.2f}"
            except:
                pass

        # UI compatibility
        data['vendor'] = data['vendor_name']

        return data
