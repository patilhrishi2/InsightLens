import fitz  # PyMuPDF  --> used to read and extract text from PDFs. Also helps detect if a PDF is text-based or image-based.
#import pytesseract  # --> OCR tool used to extract text from images.
from pdf2image import convert_from_path  # --> converts each PDF page into an image because pytesseract and EasyOCR require image input.
import pdfplumber  # --> used to extract text from PDFs with better structure retention (tables, multi-columns).
import easyocr  # --> more advanced OCR tool used as fallback when pytesseract struggles with low-quality images or complex fonts.
import numpy as np  # --> required to convert PIL images to numpy arrays as EasyOCR takes numpy arrays as input.
import os
import time  # Add at the top


# Initialize EasyOCR reader globally to avoid reloading it for each image (improves performance significantly).
reader = easyocr.Reader(['en'])

def clean_text(text):
    """
    Cleans the extracted text by replacing special unicode characters that are commonly misinterpreted.
    This step improves consistency and simplifies downstream text processing.
    """
    replacements = {
        '\u2022': '•',
        '\u00bd': '',
        '\ufb01': 'fi',
        '\u201c': '"',
        '\u201d': '"',
        '\u2013': '-',  # en dash
        '\u2014': '-',  # em dash
        '\u2019': "'"
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text

def extract_text_from_pdf(pdf_path):
    """
    Master function that performs page-wise extraction from the PDF.
    Handles mixed-content pages (which may contain both text-based and scanned image content on the same page).
    Uses both direct text extraction and OCR extraction simultaneously for each page.
    """
    start_time = time.time()  # Start timer
    doc = fitz.open(pdf_path)  # PyMuPDF document object to access the text layer.
    images = convert_from_path(pdf_path, dpi=175)  # Converts each page to an image at 175 DPI to balance OCR quality and memory usage.
    full_text = ""  # To accumulate text from all pages.

    for page_num, page in enumerate(doc):
        print(f"[INFO] Processing Page {page_num + 1}...")

        # =====================
        # Extract Text Layer
        # =====================
        # Step 1: Direct extraction using PyMuPDF (fastest text extractor).
        text_layer = page.get_text().strip()

        # Step 2: If PyMuPDF extracts too little text (could have missed complex structures like tables), fallback to pdfplumber.
        if len(text_layer.split()) < 50:  # This threshold can be adjusted based on testing.
            print("[INFO] Fallback to pdfplumber for better structure on text layer.")
            with pdfplumber.open(pdf_path) as pdf:
                text_layer = pdf.pages[page_num].extract_text() or ""  # pdfplumber extracts structured text.

        # =====================
        # Extract Image Layer (OCR)
        # =====================
        # Step 3: Get the image of the current page and save it for debugging.
        image = images[page_num]  # Fetch the image corresponding to the current page.
        # image.save(f"debug_page_{page_num + 1}.png")  # Save the image to visually inspect the content passed to OCR.

        """
        removing the pytesseract as it is not as accurate and we always end up using easy ocr
        """

        # # Step 4: Perform OCR on the image of the current page using pytesseract.
        # print("[INFO] Extracting image layer with pytesseract.")
        # ocr_text = pytesseract.image_to_string(image).strip()

        # # Step 5: If pytesseract extracts too little text (might have failed on low-quality scans), fallback to EasyOCR.
        # if len(ocr_text.split()) < 30:  # This threshold can be adjusted based on testing.
        #     print("[INFO] Fallback to EasyOCR for better OCR accuracy.")
        #     results = reader.readtext(np.array(image))  # EasyOCR needs numpy array input.
        #     ocr_text = ' '.join([result[1] for result in results])  # Extract only the recognized text from EasyOCR output.

        # New (Much faster directly):
        print("[INFO] Extracting image layer with EasyOCR (Primary).")
        results = reader.readtext(np.array(image))
        ocr_text = ' '.join([result[1] for result in results])


        # =====================
        # Combine Both Layers
        # =====================
        # Step 6: Merge the text extracted from both the text layer and the image layer.
        page_text = text_layer + "\n" + ocr_text
        full_text += page_text + "\n"

    # Clean the entire extracted text for unicode and formatting issues.
    cleaned = clean_text(full_text)

    # # Save the extracted and cleaned text for manual inspection if needed.
    # with open(pdf_path + ".extracted.txt", "w", encoding="utf-8") as f:
    #     f.write(cleaned)
    end_time = time.time()  # End timer
    extraction_time = end_time - start_time
    print(f"[TIMER] Resume extraction took {extraction_time:.2f} seconds")

    return cleaned
