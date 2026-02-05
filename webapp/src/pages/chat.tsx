import React, { useState } from "react";

export function Chat() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
        {messages.map((m, idx) => (
          <div key={idx} style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600 }}>{m.role}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
          </div>
        ))}
      </div>

      <div style={{ borderTop: "1px solid #eee", padding: 12 }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          style={{ width: "100%", resize: "none" }}
          placeholder="输入..."
        />
        <button
          onClick={() => {
            if (!input.trim()) return;
            setMessages((ms) => [...ms, { role: "user", text: input }]);
            setInput("");
          }}
          style={{ marginTop: 8 }}
        >
          发送
        </button>
      </div>
    </div>
  );
}


export default Chat;
