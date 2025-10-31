# Machine Learning Forecasting System (DEPRECATED)

> **⚠️ DEPRECATED:** This document describes the old Exponential Smoothing algorithm.  
> **Current Algorithm:** Random Forest Regressor  
> **See:** [RANDOM_FOREST_FORECASTING.md](RANDOM_FOREST_FORECASTING.md) for current implementation.

---

## Historical Documentation

Your ShelfWare forecasting previously used **Exponential Smoothing** but has been upgraded to **Random Forest** for better accuracy.

## What Was Used (Old Algorithm)

### Before Random Forest
- **ML-powered forecasting** generated predictions using Exponential Smoothing
- Uses **Exponential Smoothing** with trend and seasonality detection
- Analyzes last 90 days of sales data to predict future demand
- Falls back to database if insufficient sales history (< 7 days)

## How It Works

### 1. Data Collection
```
SELECT SalesDate, SUM(Quantity) 
FROM sales 
WHERE ProductID = ? AND SalesDate >= date('now', '-90 days')
```
Pulls the last 90 days of sales for the product.

### 2. ML Algorithm Components

**Exponential Smoothing:**
- Level smoothing (α = 0.3): tracks base demand
- Trend smoothing (β = 0.1): captures increasing/decreasing patterns

**Seasonality Detection:**
- Analyzes day-of-week patterns
- Computes average sales for Mon-Sun
- Applies seasonal adjustment to predictions

**Market Factor:**
- Recent 7-day momentum vs 90-day average
- Captures short-term demand shifts

**Confidence Scoring:**
- Based on coefficient of variation (std/mean)
- Lower variability = higher confidence
- Range: 0.5 to 0.95

### 3. Prediction Formula
```
predicted_demand = (base_level + trend × days_ahead) × season_factor
```

## API Response Format

Both endpoints now include a `source` field:

**ML-generated (sufficient data):**
```json
{
  "product_id": 123,
  "forecast_days": 30,
  "source": "ml",
  "forecasts": [...]
}
```

**Database fallback (insufficient data):**
```json
{
  "product_id": 456,
  "forecast_days": 30,
  "source": "database",
  "forecasts": [...]
}
```

## Minimum Requirements

**For ML forecasts:**
- At least 7 days of sales history in the last 90 days
- Products with < 7 days fall back to database

**For summary:**
- Analyzes up to 100 products with recent sales
- Returns top 50 by predicted 30-day demand

## Interpreting Results

### Predicted Demand
- Daily units expected for each forecast date
- Rounded to 2 decimal places

### Season Factor
- 1.0 = average day
- > 1.0 = higher demand (e.g., weekdays might be 1.15)
- < 1.0 = lower demand (e.g., weekends might be 0.85)

### Market Factor
- Recent trend indicator
- 1.0 = stable
- > 1.0 = growing demand
- < 1.0 = declining demand
- Clamped to 0.5-1.5 range

### Confidence Level
- 0.95 = very stable, predictable product
- 0.75 = moderate variability
- 0.50 = high variability, less reliable

## Performance Notes

- First call per product may take ~200-500ms (computing forecast)
- Subsequent calls use same speed (no caching yet)
- Summary endpoint processes multiple products (~2-5 seconds for 100 products)
- All computation is done in-memory (no external API calls)

## Future Improvements

**To add:**
- Response caching (5-15 min TTL)
- More sophisticated algorithms (ARIMA, Prophet)
- External factors (holidays, promotions, weather)
- Inventory constraints (don't forecast more than can be stocked)
- Price elasticity (how price changes affect demand)

**To tune:**
- Adjust α, β smoothing parameters per product category
- Longer history windows for stable products
- Shorter windows for volatile/new products
- Multi-step ahead trend adjustment

## Testing Your Forecasts

1. **Open the Forecasting page** in your browser
2. **Search for a product** (e.g., product ID 1)
3. **View the chart** - predictions are now ML-generated!
4. **Check the console** - server logs will show "ML forecast" activity
5. **Compare with old data** - if you still have the forecasts table, you can test against it

## Technical Details

**Algorithm:** Holt's Linear Exponential Smoothing + Day-of-Week Seasonality
**Libraries:** NumPy (built-in math operations), no external ML frameworks needed
**Latency:** ~100-500ms per product forecast
**Memory:** < 1MB per forecast computation

Your forecasts are now **truly predictive** and will adapt to changing sales patterns!
