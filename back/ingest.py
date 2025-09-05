# ingest.py  (drop-in replacement)
import os
import re
import csv
from pathlib import Path

# 3rd-party extractors
from bs4 import BeautifulSoup
import chardet
from pdfminer.high_level import extract_text as pdf_extract
from docx import Document
import pandas as pd

ROOT = Path(__file__).parent
# Your unified folder (as you created it)
CORPUS_DIR = ROOT / "corpus" / "air_street"
OUT_CSV = ROOT / "data" / "drive_corpus.csv"

DOC_CHAR_LIMIT = int(os.getenv("DOC_CHAR_LIMIT", "25000"))  # hard cap per file
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1800"))           # chunk size for Qdrant

def _read_bin_text(path: Path) -> str:
    """Load binary then decode using best-guess encoding."""
    with path.open("rb") as f:
        raw = f.read()
    enc = (chardet.detect(raw) or {}).get("encoding") or "utf-8"
    return raw.decode(enc, errors="ignore")

def read_file_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return pdf_extract(str(path))
        elif ext == ".docx":
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        elif ext in (".xlsx", ".xls"):
            # read all sheets as CSV-ish text
            out = []
            xls = pd.read_excel(str(path), sheet_name=None, dtype=str)
            for name, df in xls.items():
                out.append(f"# Sheet: {name}\n" + df.to_csv(index=False))
            return "\n\n".join(out)
        elif ext == ".csv":
            return _read_bin_text(path)
        elif ext in (".html", ".htm"):
            html = _read_bin_text(path)
            soup = BeautifulSoup(html, "lxml")
            return soup.get_text(" ", strip=True)
        else:
            # txt, md, json, etc.
            return _read_bin_text(path)
    except Exception as e:
        print(f"[ingest] WARN: failed to read {path}: {e}")
        return ""

def chunk_text(text: str, size: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:DOC_CHAR_LIMIT]
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size)]

def build_drive_corpus_from_folder():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    if not CORPUS_DIR.exists():
        print(f"[ingest] WARN: corpus folder not found: {CORPUS_DIR}")
        return

    print(f"[ingest] scanning: {CORPUS_DIR}")
    for p in CORPUS_DIR.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_size == 0:
                continue
        except Exception:
            pass

        txt = read_file_text(p)
        for idx, chunk in enumerate(chunk_text(txt, CHUNK_SIZE), start=1):
            # Keep the file path (relative) as "source"
            rows.append({"source": str(p.relative_to(ROOT)), "text": chunk})

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "text"])
        w.writeheader()
        w.writerows(rows)

    print(f"[ingest] wrote {len(rows)} rows → {OUT_CSV}")

if __name__ == "__main__":
    # Sheets CSV was causing crashes earlier. If you ever add one, handle it in a separate script.
    build_drive_corpus_from_folder()
    print("[ingest] Done. Now run:  python ingest_to_qdrant.py")
