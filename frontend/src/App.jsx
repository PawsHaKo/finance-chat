import { useState, useEffect } from 'react'
import './App.css'
import { PieChart, Pie, Cell, Tooltip, Legend } from 'recharts'

const API_BASE = 'http://localhost:8000'

const COLORS = [
  '#60a5fa', // blue
  '#f87171', // red
  '#34d399', // green
  '#fbbf24', // yellow
  '#a78bfa', // purple
  '#f472b6', // pink
  '#818cf8', // indigo
  '#facc15', // gold
  '#fb7185', // rose
  '#38bdf8', // sky
  '#10b981', // emerald
  '#f59e42', // orange
  '#6366f1', // violet
  '#eab308', // amber
  '#84cc16', // lime
  '#f43f5e', // pink-red
  '#0ea5e9', // cyan
  '#a3e635', // light green
  '#fcd34d', // light yellow
  '#c084fc', // light purple
  '#fca5a5', // light red
  '#fdba74', // light orange
  '#bef264', // light lime
  '#f9a8d4', // light pink
  '#6ee7b7', // mint
  '#fef08a', // pale yellow
  '#d1fae5', // pale green
  '#f3e8ff', // pale purple
  '#fef3c7', // pale gold
  '#e0e7ff', // pale indigo
]

const CASH_COLOR = '#FFD700' // gold for cash
const STOCK_COLORS = COLORS.filter(c => c !== CASH_COLOR)

function App() {
  const [symbol, setSymbol] = useState('')
  const [quantity, setQuantity] = useState('')
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [testStatus, setTestStatus] = useState(null)
  const [testLoading, setTestLoading] = useState(false)
  const [editSymbol, setEditSymbol] = useState(null)
  const [editQuantity, setEditQuantity] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingStocks, setRefreshingStocks] = useState([])
  const [cash, setCash] = useState('')
  const [cashEdit, setCashEdit] = useState('')
  const [cashLoading, setCashLoading] = useState(false)
  const [cashError, setCashError] = useState('')
  const [cashSuccess, setCashSuccess] = useState('')
  const [showCashInPie, setShowCashInPie] = useState(false)

  // Fetch portfolio and cash on mount
  const fetchPortfolio = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/`)
      if (!res.ok) throw new Error('Failed to fetch portfolio')
      const data = await res.json()
      setPortfolio(data)
      if (typeof data.cash === 'number') {
        setCash(data.cash)
        setCashEdit(data.cash)
      }
    } catch (err) {
      setError('Error fetching portfolio.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPortfolio()
  }, [])

  const fetchStockDetails = async (symbol) => {
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/${symbol}`)
      if (!res.ok) throw new Error('Failed to fetch stock details')
      return await res.json()
    } catch (err) {
      setError('Error fetching stock details.')
      return null
    }
  }

  // Add stock handler
  const handleAddStock = async (e) => {
    e.preventDefault()
    setError('')
    if (!symbol || !quantity) {
      setError('Please enter both symbol and quantity.')
      return
    }
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, quantity: parseFloat(quantity) }),
      })
      if (!res.ok) throw new Error('Failed to add stock')
      setSymbol('')
      setQuantity('')
      // Only fetch the new/updated stock's details
      const stockDetails = await fetchStockDetails(symbol.toUpperCase())
      if (!stockDetails) {
        setError('Failed to fetch details for the added stock.');
        return;
      }
      setPortfolio(prev => {
        if (!prev || !prev.stocks) return { stocks: [stockDetails], grand_total_portfolio_value: stockDetails.current_total_value || 0 }
        // If stock already exists, update it; else, add it
        const stocks = prev.stocks.filter(s => s.symbol !== stockDetails.symbol)
        stocks.push(stockDetails)
        // Recalculate grand total
        const grand_total = stocks.reduce((sum, s) => sum + (s.current_total_value || 0), 0)
        // Recalculate percentages
        stocks.forEach(s => {
          s.percentage_of_portfolio = grand_total > 0 && s.current_total_value != null ? Number(((s.current_total_value / grand_total) * 100).toFixed(2)) : null
        })
        return { stocks, grand_total_portfolio_value: Number(grand_total.toFixed(2)) }
      })
    } catch (err) {
      setError('Error adding stock.')
    }
  }

  const handleTestConnection = async () => {
    setTestLoading(true)
    setTestStatus(null)
    try {
      const res = await fetch(`${API_BASE}/test-connection`)
      const data = await res.json()
      setTestStatus(data)
    } catch (err) {
      setTestStatus({ status: 'error', message: 'Failed to connect to backend.' })
    } finally {
      setTestLoading(false)
    }
  }

  const handleEditClick = (stock) => {
    setEditSymbol(stock.symbol)
    setEditQuantity(stock.quantity)
  }

  const handleEditSave = async (symbol) => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/${symbol}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, quantity: parseFloat(editQuantity) }),
      })
      if (!res.ok) throw new Error('Failed to update stock')
      setEditSymbol(null)
      setEditQuantity('')
      // Only fetch the updated stock's details
      const stockDetails = await fetchStockDetails(symbol)
      if (!stockDetails) {
        setError('Failed to fetch details for the updated stock.');
        return;
      }
      setPortfolio(prev => {
        if (!prev || !prev.stocks) return { stocks: [stockDetails], grand_total_portfolio_value: stockDetails.current_total_value || 0 }
        const stocks = prev.stocks.map(s => s.symbol === stockDetails.symbol ? stockDetails : s)
        // Recalculate grand total
        const grand_total = stocks.reduce((sum, s) => sum + (s.current_total_value || 0), 0)
        // Recalculate percentages
        stocks.forEach(s => {
          s.percentage_of_portfolio = grand_total > 0 && s.current_total_value != null ? Number(((s.current_total_value / grand_total) * 100).toFixed(2)) : null
        })
        return { stocks, grand_total_portfolio_value: Number(grand_total.toFixed(2)) }
      })
    } catch (err) {
      setError('Error updating stock.')
    }
  }

  const handleDelete = async (symbol) => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/${symbol}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Failed to delete stock')
      // Update portfolio locally instead of refetching
      setPortfolio(prev => {
        if (!prev || !prev.stocks) return prev
        const stocks = prev.stocks.filter(s => s.symbol !== symbol)
        // Recalculate grand total
        const grand_total = stocks.reduce((sum, s) => sum + (s.current_total_value || 0), 0)
        // Recalculate percentages
        stocks.forEach(s => {
          s.percentage_of_portfolio = grand_total > 0 && s.current_total_value != null ? Number(((s.current_total_value / grand_total) * 100).toFixed(2)) : null
        })
        return { stocks, grand_total_portfolio_value: Number(grand_total.toFixed(2)) }
      })
    } catch (err) {
      setError('Error deleting stock.')
    }
  }

  // New: Refresh prices only (keep table visible, show spinner in price/value columns)
  const refreshPrices = async () => {
    if (!portfolio || !portfolio.stocks) return
    setRefreshing(true)
    setRefreshingStocks(portfolio.stocks.map(s => s.symbol))
    setError('')
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/refresh`)
      if (!res.ok) throw new Error('Failed to refresh prices')
      const data = await res.json()
      setPortfolio(data)
    } catch (err) {
      setError('Error refreshing prices.')
    } finally {
      setRefreshing(false)
      setRefreshingStocks([])
    }
  }

  // Prepare data for Pie Chart
  let chartData = (portfolio?.stocks || [])
    .filter(stock => stock.percentage_of_portfolio != null && stock.percentage_of_portfolio > 0)
    .map((stock, idx) => ({
      name: stock.symbol,
      value: stock.current_total_value || 0,
      color: STOCK_COLORS[idx % STOCK_COLORS.length]
    }))

  if (showCashInPie && typeof cash === 'number' && cash > 0) {
    chartData = [
      ...chartData,
      {
        name: 'Cash',
        value: cash,
        color: CASH_COLOR
      }
    ]
  }

  // Cash handlers
  const handleCashChange = (e) => {
    setCashEdit(e.target.value)
    setCashError('')
    setCashSuccess('')
  }

  const saveCashBalance = async () => {
    setCashLoading(true)
    setCashError('')
    setCashSuccess('')
    try {
      const value = parseFloat(cashEdit)
      if (isNaN(value) || value < 0) {
        setCashError('Please enter a valid non-negative number.')
        setCashLoading(false)
        return
      }
      const res = await fetch(`${API_BASE}/portfolio/cash/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cash: value })
      })
      if (!res.ok) throw new Error('Failed to update cash')
      const data = await res.json()
      setCash(data.cash)
      setCashEdit(data.cash)
      setCashSuccess('Cash balance updated!')
      // Optionally refresh portfolio to update grand total
      fetchPortfolio()
    } catch (err) {
      setCashError('Error updating cash balance.')
    } finally {
      setCashLoading(false)
    }
  }

  return (
    <div className="flex-row">
      <div className="container">
        <h1>Finance Portfolio Tool</h1>
        {/* Cash Balance Section */}
        <div className="cash-balance-section" style={{ marginBottom: '1.5em', display: 'flex', alignItems: 'center', gap: '1em' }}>
          <label htmlFor="cash-balance" style={{ fontWeight: 600 }}>Cash Balance:</label>
          <input
            type="number"
            id="cash-balance"
            value={cashEdit}
            min="0"
            step="0.01"
            onChange={handleCashChange}
            style={{ width: '120px', fontSize: '1.1em', padding: '0.3em 0.7em' }}
            disabled={cashLoading}
          />
          <button onClick={saveCashBalance} disabled={cashLoading} className="primary-btn">
            {cashLoading ? 'Saving...' : 'Save'}
          </button>
          {cashError && <span className="error" style={{ marginLeft: '1em' }}>{cashError}</span>}
          {cashSuccess && <span className="success" style={{ marginLeft: '1em', color: '#34d399' }}>{cashSuccess}</span>}
        </div>
        <div className="actions-row">
          <div className="secondary-actions">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7em' }}>
              <button onClick={refreshPrices} disabled={refreshing}>
                {refreshing ? 'Refreshing...' : 'Refresh Prices'}
              </button>
              <button onClick={handleTestConnection} disabled={testLoading}>
                {testLoading ? 'Testing...' : 'Test API Connection'}
              </button>
              {testStatus && (
                <div className={testStatus.status === 'success' ? 'success' : 'error'} style={{margin: 0, minWidth: '200px', textAlign: 'left'}}>
                  {testStatus.message} {testStatus.price ? `(Sample price: $${testStatus.price})` : ''}
                </div>
              )}
            </div>
          </div>
        </div>
        <form onSubmit={handleAddStock} className="add-stock-form">
          <input
            type="text"
            placeholder="Stock Symbol (e.g. AAPL)"
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
          />
          <input
            type="number"
            placeholder="Quantity"
            value={quantity}
            min="0"
            step="any"
            onChange={e => setQuantity(e.target.value)}
          />
          <button type="submit" className="primary-btn">Add Stock</button>
        </form>
        <div className="table-container">
          {error && <div className="error">{error}</div>}
          {loading ? (
            <div>Loading portfolio...</div>
          ) : portfolio && portfolio.stocks && portfolio.stocks.length > 0 ? (
            <table className="portfolio-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Current Price</th>
                  <th>Total Value</th>
                  <th>% of Portfolio</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.stocks.map(stock => (
                  <tr key={stock.symbol}>
                    <td>{stock.symbol}</td>
                    <td>
                      {editSymbol === stock.symbol ? (
                        <input
                          type="number"
                          value={editQuantity}
                          min="0"
                          step="any"
                          onChange={e => setEditQuantity(e.target.value)}
                          style={{ width: '70px' }}
                        />
                      ) : (
                        stock.quantity
                      )}
                    </td>
                    <td>
                      {refreshingStocks.includes(stock.symbol) && refreshing ? (
                        <span className="price-spinner"></span>
                      ) : (
                        stock.current_price !== null ? `$${stock.current_price.toFixed(2)}` : 'N/A'
                      )}
                    </td>
                    <td>
                      {refreshingStocks.includes(stock.symbol) && refreshing ? (
                        <span className="price-spinner"></span>
                      ) : (
                        stock.current_total_value !== null ? `$${stock.current_total_value.toFixed(2)}` : 'N/A'
                      )}
                    </td>
                    <td>
                      {refreshingStocks.includes(stock.symbol) && refreshing ? (
                        <span className="price-spinner"></span>
                      ) : (
                        stock.percentage_of_portfolio !== null ? `${stock.percentage_of_portfolio}%` : 'N/A'
                      )}
                    </td>
                    <td>
                      {editSymbol === stock.symbol ? (
                        <div className="action-buttons">
                          <button className="action-btn edit" onClick={() => handleEditSave(stock.symbol)}>Save</button>
                          <button className="action-btn" onClick={() => setEditSymbol(null)}>Cancel</button>
                        </div>
                      ) : (
                        <div className="action-buttons">
                          <button className="action-btn edit" onClick={() => handleEditClick(stock)}>Edit</button>
                          <button className="action-btn delete" onClick={() => handleDelete(stock.symbol)}>Delete</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="4"><strong>Grand Total</strong></td>
                  <td>{refreshing ? <span className="price-spinner"></span> : `$${portfolio.grand_total_portfolio_value}`}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          ) : (
            <div>No stocks in portfolio yet.</div>
          )}
        </div>
      </div>
      {chartData.length > 0 && (
        <div className="container pie-chart-container">
          <h1>Portfolio Pie Chart</h1>
          <div style={{ marginBottom: '1em' }}>
            <label style={{ fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={showCashInPie}
                onChange={e => setShowCashInPie(e.target.checked)}
                style={{ marginRight: '0.5em' }}
              />
              Show cash in pie chart
            </label>
          </div>
          <PieChart width={350} height={250}>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </div>
      )}
    </div>
  )
}

export default App
