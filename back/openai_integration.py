# openai_integration.py
import os, time, random, requests
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Put it in back/.env")

_client = OpenAI(api_key=OPENAI_API_KEY)

def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("1","true","yes","on"):  return True
    if v in ("0","false","no","off"): return False
    return default

def _parse_domains(s: str) -> List[str]:
    return [d.strip() for d in (s or "").split(",") if d.strip()]

def _gather_urls_from_response_dict(d: Any) -> List[str]:
    urls = []
    if isinstance(d, dict):
        for k,v in d.items():
            if k == "url" and isinstance(v,str) and v.startswith("http"):
                urls.append(v)
            else:
                urls.extend(_gather_urls_from_response_dict(v))
    elif isinstance(d, list):
        for item in d:
            urls.extend(_gather_urls_from_response_dict(item))
    return urls

def web_answer(
    question: str,
    allowed_domains: Optional[List[str]] = None,
    context_size: Optional[str] = None,
    location: Optional[Dict[str,str]] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Web search via OpenAI Responses API. We DO NOT use 'filters' (to avoid 400s).
    If domains are provided, we inject a 'site:' clause into the prompt.
    Returns: {"text": ..., "sources": [urls]}
    """
    if not _env_bool("ENABLE_WEB_SEARCH", True):
        return {"text": "", "sources": []}

    mdl = model or (os.getenv("WEB_MODEL") or "gpt-4.1")
    allowed_domains = allowed_domains or _parse_domains(os.getenv("WEB_ALLOWED_DOMAINS",""))

    # Prompt with domain scoping (works for all models)
    scoped_q = question
    if allowed_domains:
        domain_clause = " OR ".join([f"site:{d}" for d in allowed_domains])
        scoped_q = f"{question}\n\nSearch constraint: ({domain_clause})"

    # Optional location hint
    tool_cfg: Dict[str, Any] = {"type": "web_search"}
    country = (os.getenv("WEB_LOCATION_COUNTRY") or "").strip()
    city    = (os.getenv("WEB_LOCATION_CITY") or "").strip()
    region  = (os.getenv("WEB_LOCATION_REGION") or "").strip()
    if country or city or region:
        tool_cfg["user_location"] = {"type": "approximate"}
        if country: tool_cfg["user_location"]["country"] = country
        if city:    tool_cfg["user_location"]["city"]    = city
        if region:  tool_cfg["user_location"]["region"]  = region

    # Context size hint (harmless if ignored)
    tool_cfg["search_context_size"] = (context_size or os.getenv("WEB_CONTEXT_SIZE","medium"))

    # Call
    resp = _client.responses.create(
        model=mdl,
        tools=[tool_cfg],
        tool_choice="auto",
        include=["web_search_call.action.sources"],
        input=scoped_q,
    )

    # Extract text
    text = getattr(resp, "output_text", "") or ""
    # Extract any cited/source URLs
    try:
        resp_dict = resp.to_dict() if hasattr(resp, "to_dict") else resp
    except Exception:
        resp_dict = getattr(resp, "model_dump", lambda: {})()
    urls = list(dict.fromkeys(_gather_urls_from_response_dict(resp_dict)))

    return {"text": text.strip(), "sources": urls}

# --- Embeddings + chat (grounded) ---

BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
_DEFAULT_HEADERS = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

def _headers(): return _DEFAULT_HEADERS

def _post_with_retry(url: str, json_payload: dict, timeout: int = 120, max_retries: int = 3):
    backoff = 1.5
    for i in range(max_retries):
        r = requests.post(url, headers=_headers(), json=json_payload, timeout=timeout)
        if r.status_code in (429,500,502,503,504) and i < max_retries-1:
            time.sleep(backoff ** (i+1)); continue
        r.raise_for_status(); return r
    r.raise_for_status(); return r

def embed_text(text: str):
    """text-embedding-3-small (1536 dims)"""
    url = f"{BASE_URL}/embeddings"
    payload = {"model": "text-embedding-3-small", "input": text}
    r = _post_with_retry(url, payload, timeout=60)
    return r.json()["data"][0]["embedding"]

_CLOSERS = [
    "Would you like a quick example from the dataset?",
    "Want me to expand on one point?",
    "Should I list a few key takeaways?",
    "Want this summarized even shorter?",
    "Shall I compare this with another channel?",
]
def _closer(): return random.choice(_CLOSERS)

def chat_answer(context: str, question: str, temperature: float = 0.2) -> str:
    """Answer ONLY from provided context."""
    system = (
        "You are the AM/SM knowledge bot. Answer ONLY using the supplied context. "
        "If the context is insufficient, say: 'I don’t know from the current dataset.' "
        "No guessing; no invented examples.\n\n"
        "Formatting:\n"
        "- Lists: concise bullets (max 8)\n"
        "- Summaries: 2–3 sentences\n"
        "- Comparisons/strategies: short paragraphs\n"
        "- Do NOT include raw URLs or a 'Sources:' block."
    )
    user = f"Question: {question}\n\nContext (use this to answer; if it's not enough, say you don't know):\n{context}"
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": os.getenv("CHAT_MODEL","gpt-4o-mini"),
        "temperature": temperature,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
    }
    r = _post_with_retry(url, payload, timeout=120)
    msg = (r.json()["choices"][0]["message"]["content"] or "").strip()
    c = _closer()
    if c not in msg: msg = (msg + "\n\n" + c).strip()
    return msg
