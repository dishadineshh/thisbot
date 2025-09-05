import React, { useState, useRef, useEffect } from "react";
import "./App.css";
import { ask } from "./api";

export default function App() {
  const [messages, setMessages] = useState([
    { role: "bot", text: "Hi! I’m your company’s knowledge companion. Ask me anything about projects, updates, changes, or history — I’ve got it all." }
  ]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send() {
    const q = question.trim();
    if (!q || sending) return;
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setSending(true);

    try {
      const res = await ask(q);
      const text = res.answer?.trim() || "I couldn’t find that in the current dataset.";
      setMessages((m) => [...m, { role: "bot", text }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "bot", text: `Error: ${e.message}` }]);
    } finally {
      setSending(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-badge">A</div>
          <h1>AM/SM BOT</h1>
        </div>

        <button className="new-chat" onClick={() => {
          setMessages([{ role: "bot", text: "New chat started. How can I help?" }]);
        }}>
          + New Chat
        </button>

        <div className="history-title">Conversation History</div>
        <div className="history small">
          (Your recent questions will appear here in a future update.)
        </div>
      </aside>

      <main className="main">
        <div className="header">
          <div className="title">AM/SM BOT</div>

          {/* Sticky note with web-search trigger hint */}
          <div className="sticky-note">
            <strong>Need live info?</strong> Add any of these words to your question to trigger web search:
            <div className="note-keys">
              {["today","latest","this week","breaking","current","news","2025"].map((k)=>(
                <span key={k} className="note-pill">{k}</span>
              ))}
            </div>
            <div className="small" style={{marginTop:6}}>Example: “latest guidance on GA4 consent banners”</div>
          </div>
        </div>

        <div className="chat" ref={chatRef}>
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role === "user" ? "user" : "bot"}`}>
              {m.text}
            </div>
          ))}
        </div>

        <div className="inputbar">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            placeholder='Ask about your data… (try "top countries last 7 days")'
          />
          <button onClick={send} disabled={sending}>{sending ? "Sending…" : "Send"}</button>
        </div>
      </main>
    </div>
  );
}
