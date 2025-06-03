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

function getPortfolioSummary(portfolio) {
  if (!portfolio || !portfolio.stocks) return 'No portfolio data available.';
  const total = portfolio.grand_total_portfolio_value || 0;
  const cash = typeof portfolio.cash === 'number' ? portfolio.cash : null;
  let summary = `Your portfolio total value is **$${total.toLocaleString()}**.`;
  if (cash !== null) summary += `\n\nCash balance: **$${cash.toLocaleString()}**.`;
  if (portfolio.stocks.length > 0) {
    summary += '\n\n**Holdings:**';
    summary += '\n' + portfolio.stocks.map(s => `- **${s.symbol}**: ${s.quantity} shares, $${s.current_total_value?.toLocaleString() || 'N/A'} (${s.percentage_of_portfolio || 0}% of portfolio)`).join('\n');
  }
  return summary;
}

export default function AssistantChatPopup({ onClose, portfolio }) {
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
    // Simulate assistant reply with portfolio data if relevant
    setTimeout(() => {
      let reply;
      if (/portfolio|holdings|total|cash|balance|stock|summary|what do i have|my investments/i.test(trimmed)) {
        reply = getPortfolioSummary(portfolio);
      } else {
        reply = `You said: **${trimmed}**\n\n(Portfolio answers coming soon!)`;
      }
      setMessages(msgs => [...msgs, { role: 'assistant', content: reply }]);
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