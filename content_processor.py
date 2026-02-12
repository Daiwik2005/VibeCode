import hashlib
import time
import os
import fitz
import pandas as pd
from docx import Document
from sentence_transformers import SentenceTransformer
from semantic_intelligence import FILES

MODEL = SentenceTransformer("all-MiniLM-L6-v2")

SUPPORTED_EXTENSIONS = (
    ".pdf", ".txt", ".docx", ".csv",
    ".md", ".py", ".java", ".cpp", ".c", ".js"
)

IGNORE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".mp3", ".wav",
    ".mp4", ".avi", ".mov"
)

def wait_until_stable(path, checks=3, delay=1.0):
    last = -1
    for _ in range(checks):
        try:
            size = os.path.getsize(path)
            if size == last:
                return True
            last = size
            time.sleep(delay)
        except:
            return False
    return True

def extract_text(path):
    ext = path.lower()

    if ext.endswith(".pdf"):
        doc = fitz.open(path)
        text = "".join(p.get_text() for p in doc)
        doc.close()
        return text

    if ext.endswith(".docx"):
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    if ext.endswith(".csv"):
        df = pd.read_csv(path)
        return df.to_string()

    return open(path, encoding="utf-8", errors="ignore").read()

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def process_file(path, root_dir):
    path = str(path)

    if not path.startswith(str(root_dir)):
        return

    if not path.lower().endswith(SUPPORTED_EXTENSIONS):
        return

    if path.lower().endswith(IGNORE_EXTENSIONS):
        return

    if not wait_until_stable(path):
        return

    text = extract_text(path)
    if not text.strip():
        return

    print(f"[Content] Processing {path}")

    FILES[path] = {
        "hash": file_hash(path),
        "embedding": MODEL.encode(text),
        "text": text,
        "cluster": None
    }

def remove_file(path, root_dir):
    FILES.pop(str(path), None)
