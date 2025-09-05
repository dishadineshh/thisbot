# ingest_to_qdrant.py — push data/drive_corpus.csv to Qdrant
import os
import csv
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

# Reuse your OpenAI embed function
from openai_integration import embed_text

load_dotenv()

ROOT = Path(__file__).parent
CSV_PATH = ROOT / "data" / "drive_corpus.csv"

QDRANT_URL        = (os.getenv("QDRANT_URL") or "").rstrip("/")
QDRANT_API_KEY    = os.getenv("QDRANT_API_KEY") or ""
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION") or "am_sm_corpus"
VECTOR_SIZE       = int(os.getenv("QDRANT_VECTOR_SIZE") or "1536")

HDRS = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

def _q(url, method="GET", json=None, timeout=60):
    r = requests.request(method, url, headers=HDRS, json=json, timeout=timeout)
    r.raise_for_status()
    return r.json()

def ensure_collection():
    # create collection if missing
    info_url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}"
    try:
        _q(info_url, "GET")
        print(f"[qdrant] collection exists: {QDRANT_COLLECTION}")
        return
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 404:
            raise

    print(f"[qdrant] creating collection: {QDRANT_COLLECTION}")
    create_url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}"
    payload = {
        "vectors": {"size": VECTOR_SIZE, "distance": "Cosine"},
    }
    _q(create_url, "PUT", json=payload)
    print("[qdrant] created.")

def upsert_batch(points):
    """points: list of {id, vector, payload}"""
    if not points:
        return
    url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?wait=true"
    payload = {"points": points}
    _q(url, "PUT", json=payload)

def main():
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise SystemExit("Missing QDRANT_URL or QDRANT_API_KEY in .env")

    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH} — run `python ingest.py` first")

    ensure_collection()

    # read rows
    rows = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            txt = (r.get("text") or "").strip()
            src = (r.get("source") or "").strip()
            if txt:
                rows.append({"source": src, "text": txt})

    if not rows:
        raise SystemExit("No rows in CSV to ingest.")

    print(f"[ingest] rows to upsert: {len(rows)}")

    batch, count = [], 0
    for row in rows:
        vec = embed_text(row["text"])  # 1536-d from OpenAI
        pid = str(uuid.uuid4())
        point = {
            "id": pid,
            "vector": vec,
            "payload": {
                "source": row["source"],
                "text": row["text"],
                "brand": "AM/SM"
            },
        }
        batch.append(point)

        if len(batch) >= 64:
            upsert_batch(batch)
            count += len(batch)
            print(f"[ingest] upserted: {count}")
            batch = []
            # be gentle on the API
            time.sleep(0.2)

    if batch:
        upsert_batch(batch)
        count += len(batch)
        print(f"[ingest] upserted: {count}")

    print("Done.")

if __name__ == "__main__":
    main()
