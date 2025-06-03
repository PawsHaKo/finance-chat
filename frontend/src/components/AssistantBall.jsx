import React from 'react';
import './AssistantBall.css';

export default function AssistantBall({ onClick, disabled }) {
  return (
    <button
      className="assistant-ball"
      aria-label="Open assistant chat"
      onClick={onClick}
      tabIndex={disabled ? -1 : 0}
      disabled={disabled}
    >
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="12" fill="url(#gradient)" />
        <path d="M7 10h10M7 14h6" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
        <defs>
          <linearGradient id="gradient" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
            <stop stopColor="#60a5fa" />
            <stop offset="1" stopColor="#2563eb" />
          </linearGradient>
        </defs>
      </svg>
    </button>
  );
} 