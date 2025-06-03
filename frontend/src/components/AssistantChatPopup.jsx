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
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Scroll to bottom when messages change
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, typing]);

  const handleInputChange = (e) => setInput(e.target.value);

  const handleSend = async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setMessages(msgs => [...msgs, { role: 'user', content: trimmed }]);
    setInput('');
    setTyping(true);
    setError('');
    try {
      const resp = await fetch('http://localhost:8000/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            ...messages,
            { role: 'user', content: trimmed }
          ],
          portfolio
        })
      });
      if (!resp.ok) throw new Error('Failed to get assistant reply');
      const data = await resp.json();
      setMessages(msgs => [...msgs, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      setMessages(msgs => [...msgs, { role: 'assistant', content: 'Sorry, there was an error getting my response.' }]);
      setError('Error contacting assistant.');
    } finally {
      setTyping(false);
    }
  };

  return (
    <div className={`assistant-chat-popup${expanded ? ' expanded' : ''}`}>
      <div className="assistant-chat-header">
        <span>Assistant</span>
        <div style={{ display: 'flex', gap: '0.5em' }}>
          <button
            className="assistant-chat-expand"
            onClick={() => setExpanded(e => !e)}
            aria-label={expanded ? 'Restore chat size' : 'Expand chat'}
            tabIndex={0}
          >
            {expanded ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M7 17h4v-2H9v-2h2v-2H7v6zm6-6v2h2v2h-2v2h4v-6h-4z" fill="#fff"/></svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M7 7h4v2H9v2h2v2H7V7zm6 0v2h2v2h-2v2h4V7h-4z" fill="#fff"/></svg>
            )}
          </button>
          <button className="assistant-chat-close" onClick={onClose} aria-label="Close chat">×</button>
        </div>
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
      {error && <div className="error" style={{margin: '0.5em 1em'}}>{error}</div>}
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