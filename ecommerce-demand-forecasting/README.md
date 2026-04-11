MVP for Demand Forecasting Tool for Household Item Manufacturer

Problem: As a producer of household items, I manage inventory data, historical sales data, and historical purchasing data from multiple sources (Amazon, FBA, Walmart, Shopify, and internal trackers). I need a forecasting tool to predict demand accurately and determine optimal times to order more items from suppliers, reducing stockouts and excess inventory.

Features:
- Enable user authentication and secure CSV data upload from Amazon, FBA, Walmart, Shopify, and internal inventory/purchasing trackers.
- Integrate data from multiple sources into a unified dataset for forecasting.
- Provide basic statistical forecasting models (e.g., ARIMA or Exponential Smoothing) to predict demand for household items.
- Generate simple, user-friendly dashboards to visualize demand forecasts and inventory levels.
- Offer alerts for reorder points based on forecasted demand and current inventory.
- Support basic scenario planning to adjust forecasts for promotions or seasonal trends.
- Provide exportable reports in CSV format for sharing forecasts with stakeholders.

Technical specs:
- create a fully functional Flask application backed onto a SQlite database using SqlAlchemy for ORM and database migrations. 
- the only data-integration pattern is CSV import and export. Keep it simple.
