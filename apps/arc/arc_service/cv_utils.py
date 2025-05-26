import logging
logger = logging.getLogger('arc')
from fastapi import UploadFile
import pdfplumber
from docx import Document
import re
import spacy
import tiktoken

SECTION_HEADERS = [
    r"work experience", r"professional experience", r"employment history",
    r"education", r"academic background",
    r"skills", r"technical skills",
    r"projects", r"certifications", r"training"
]

section_header_regex = re.compile(rf"^({'|'.join(SECTION_HEADERS)})[:\s]*$", re.IGNORECASE | re.MULTILINE)

def split_cv_by_sections(text):
    matches = list(section_header_regex.finditer(text))
    if not matches:
        logging.info("[SECTION SPLIT] No section headers found. Treating entire CV as one section.")
        return [("full", text)]
    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        header = match.group(1).strip().lower()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        logging.info(f"[SECTION SPLIT] Found section header: '{header}' (chars {start}-{end})")
        sections.append((header, section_text))
    return sections

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

def nlp_chunk_text(text, max_tokens=8000, model="gpt-4-turbo"):
    nlp = spacy.load("en_core_web_sm")
    enc = tiktoken.encoding_for_model(model)
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    chunks = []
    current_chunk = []
    current_tokens = 0
    for sent in sentences:
        sent_tokens = len(enc.encode(sent))
        if current_tokens + sent_tokens > max_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_tokens = sent_tokens
        else:
            current_chunk.append(sent)
            current_tokens += sent_tokens
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    logger.info(f"[NLP CHUNKING] Created {len(chunks)} chunks (max {max_tokens} tokens each)")
    for i, chunk in enumerate(chunks):
        logger.info(f"[NLP CHUNKING] Chunk {i+1} token count: {len(enc.encode(chunk))}")
    return chunks 