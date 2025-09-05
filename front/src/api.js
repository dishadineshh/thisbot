// Minimal API helper used by App.js
const API_BASE = process.env.REACT_APP_API_BASE || ""; // e.g. "" or "http://localhost:8000"

export async function ask(question, opts = {}) {
  const payload = {
    question,
    ...(opts.web ? { web: true } : {}),
    ...(opts.web_domains ? { web_domains: opts.web_domains } : {}),
  };

  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = await res.text();
    throw new Error(`API ${res.status}: ${msg}`);
  }
  return res.json();
}
