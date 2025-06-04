import React from 'react';
import './ThemeToggleBall.css'; // 使用同一份樣式

export default function ThemeToggleBall({ theme, toggleTheme }) {
    return (
        <button
            className="toggle-theme-ball"
            aria-label="Toggle theme"
            onClick={toggleTheme}
        >
      <span style={{ fontSize: '24px' }}>
        {theme === 'dark' ? '🌙' : '☀️'}
      </span>
        </button>
    );
}