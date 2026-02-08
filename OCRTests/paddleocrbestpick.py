import os
import re

OUTPUT_DIR = "output"
BEST_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "best")
os.makedirs(BEST_OUTPUT_DIR, exist_ok=True)

# Define what is considered "valid" text characters
valid_chars_pattern = re.compile(r"[a-zA-Z0-9\s.,%$-]")

# Collect all text files
all_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".txt")]

# Group by page number
pages_dict = {}
for f in all_files:
    match = re.match(r"page(\d+)_", f)
    if match:
        page_no = int(match.group(1))
        pages_dict.setdefault(page_no, []).append(f)

# Score and pick best per page
for page_no, files in pages_dict.items():
    best_score = -1
    best_text = ""
    best_file = ""

    for file in files:
        path = os.path.join(OUTPUT_DIR, file)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        # Score heuristics
        num_words = len(text.split())
        num_valid_chars = len(valid_chars_pattern.findall(text))
        num_garbage_chars = len(text) - num_valid_chars
        score = num_words + num_valid_chars - num_garbage_chars

        if score > best_score:
            best_score = score
            best_text = text
            best_file = file

    # Save the best text for this page
    best_path = os.path.join(BEST_OUTPUT_DIR, f"page_{page_no}_best.txt")
    with open(best_path, "w", encoding="utf-8") as f:
        f.write(best_text)

    print(f"Page {page_no}: Best OCR file = {best_file}, score = {best_score}")

print("Best OCR selection completed.")
