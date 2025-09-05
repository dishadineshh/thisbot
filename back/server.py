# server.py
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

# Load .env sitting next to this file
ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH)

# Boot logs
print(f"[boot] QDRANT_URL={os.getenv('QDRANT_URL')}")
k = (os.getenv("QDRANT_API_KEY") or "").strip()
print(f"[boot] QDRANT_API_KEY prefix={k[:8]} len={len(k)}")
print(f"[boot] WEB_MODEL={os.getenv('WEB_MODEL','gpt-4.1')}")

from openai_integration import embed_text, chat_answer, web_answer
from qdrant_rest import search

def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("1","true","yes","on"):  return True
    if v in ("0","false","no","off"): return False
    return default

# Config
PORT                = int(os.getenv("PORT", "8000"))
CORS_ORIGINS        = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
SHOW_SOURCES        = _env_bool("SHOW_SOURCES", False)
TOP_K               = int(os.getenv("TOP_K", "24"))
MAX_CONTEXT_CHARS   = int(os.getenv("MAX_CONTEXT_CHARS", "24000"))
ENABLE_WEB_SEARCH   = _env_bool("ENABLE_WEB_SEARCH", True)

app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)

@app.get("/status")
def status():
    return jsonify({"ok": True})

@app.post("/ask")
def ask():
    try:
        data = request.get_json(force=True) or {}
        q = (data.get("question") or "").strip()
        if not q:
            return jsonify({"error": "Missing question"}), 400

        use_web     = bool(data.get("web"))
        web_domains = data.get("web_domains") or []
        q_lower     = q.lower()

        # 1) Vector search first
        qvec   = embed_text(q)
        hits   = search(qvec, top_k=TOP_K)
        chunks = [h.get("payload", {}).get("text","") for h in hits if h.get("payload")]
        context = "\n\n---\n\n".join([c for c in chunks if c])[:MAX_CONTEXT_CHARS]
        sources = list(dict.fromkeys([
            h.get("payload", {}).get("source","") for h in hits if h.get("payload")
        ]))

        # 2) If user wants fresh info or we have no context, try web
        wants_fresh = any(kw in q_lower for kw in ["today","latest","this week","breaking","current","news","2025"])
        if ENABLE_WEB_SEARCH and (use_web or wants_fresh or not context.strip()):
            wa = web_answer(question=q, allowed_domains=web_domains if web_domains else None)
            if (wa.get("text") or "").strip():
                out = {"answer": wa["text"]}
                out["sources"] = (sources + wa.get("sources", [])) if SHOW_SOURCES else wa.get("sources", [])
                return jsonify(out)

        # 3) If we have corpus context, answer with grounding
        if context.strip():
            ans = (chat_answer(context, q, temperature=0.2) or "").strip()
            return jsonify({"answer": ans, "sources": sources if SHOW_SOURCES else []})

        # 4) Nothing found anywhere
        return jsonify({"answer": "I don’t know from the current dataset.", "sources": []})

    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}", "answer": "", "sources": []}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
