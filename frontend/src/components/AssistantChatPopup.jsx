import React, { useState, useRef, useEffect } from 'react';
import './AssistantChatPopup.css';

function renderMarkdown(text) {
  // Very basic markdown: **bold**, `code`, [link](url)
  let html = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return { __html: html };
}

export default function AssistantChatPopup({ onClose }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I\'m your portfolio assistant. Ask me anything about your investments.' }
  ]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Scroll to bottom when messages change
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, typing]);

  const handleInputChange = (e) => setInput(e.target.value);

  const handleSend = (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setMessages(msgs => [...msgs, { role: 'user', content: trimmed }]);
    setInput('');
    setTyping(true);
    // Simulate assistant reply
    setTimeout(() => {
      setMessages(msgs => [...msgs, { role: 'assistant', content: `You said: **${trimmed}**\n\n(Portfolio answers coming soon!)` }]);
      setTyping(false);
    }, 1200);
  };

  return (
    <div className="assistant-chat-popup">
      <div className="assistant-chat-header">
        <span>Assistant</span>
        <button className="assistant-chat-close" onClick={onClose} aria-label="Close chat">×</button>
      </div>
      <div className="assistant-chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`assistant-msg ${msg.role}`}>
            <span dangerouslySetInnerHTML={renderMarkdown(msg.content)} />
          </div>
        ))}
        {typing && (
          <div className="assistant-msg assistant typing-indicator">
            <span>Assistant is typing<span className="dot">.</span><span className="dot">.</span><span className="dot">.</span></span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <form className="assistant-chat-input-row" onSubmit={handleSend}>
        <input
          type="text"
          className="assistant-chat-input"
          placeholder="Type your message..."
          value={input}
          onChange={handleInputChange}
          autoFocus
          disabled={typing}
        />
        <button type="submit" className="assistant-chat-send" disabled={!input.trim() || typing}>Send</button>
      </form>
    </div>
  );
} 