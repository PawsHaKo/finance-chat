import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

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

  // Fetch portfolio on mount and after adding stock
  const fetchPortfolio = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/portfolio/stocks/`)
      if (!res.ok) throw new Error('Failed to fetch portfolio')
      const data = await res.json()
      setPortfolio(data)
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
      fetchPortfolio()
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

  return (
    <div className="container">
      <h1>Finance Portfolio Tool</h1>
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
        <button type="submit">Add Stock</button>
      </form>
      <button onClick={handleTestConnection} disabled={testLoading} style={{marginBottom: '1em'}}>
        {testLoading ? 'Testing...' : 'Test API Connection'}
      </button>
      <button onClick={refreshPrices} disabled={refreshing} style={{marginBottom: '1em', marginLeft: '1em'}}>
        {refreshing ? 'Refreshing...' : 'Refresh Prices'}
      </button>
      {testStatus && (
        <div className={testStatus.status === 'success' ? 'success' : 'error'}>
          {testStatus.message} {testStatus.price ? `(Sample price: $${testStatus.price})` : ''}
        </div>
      )}
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
  )
}

export default App
