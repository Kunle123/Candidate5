import logging
from fastapi import UploadFile
import pdfplumber
from docx import Document

def extract_text_from_pdf(file: UploadFile):
    try:
        with pdfplumber.open(file.file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        file.file.seek(0)
        if not text.strip():
            logging.error("[PDF EXTRACT] No text extracted from PDF file.")
        return text
    except Exception as e:
        logging.error(f"[PDF EXTRACT] Exception during PDF extraction: {e}")
        file.file.seek(0)
        return ""

def extract_text_from_docx(file: UploadFile):
    try:
        doc = Document(file.file)
        text = "\n".join([para.text for para in doc.paragraphs])
        file.file.seek(0)
        if not text.strip():
            logging.error("[DOCX EXTRACT] No text extracted from DOCX file.")
        return text
    except Exception as e:
        logging.error(f"[DOCX EXTRACT] Exception during DOCX extraction: {e}")
        file.file.seek(0)
        return "" 