# ShelfWare Bundle

This folder contains a self-contained runnable version of ShelfWare (backend + UI) with the SQLite database colocated.

What’s inside:
- unified_api_server.py — Flask API server
- employees.db — SQLite database used by the app
- *.html — All pages (admin, inventory, forecasting, procurement, customer, login)
- *.css — Page styles
- *.png — Logo assets

CSV files are intentionally not included here (kept at the project root) as requested.

## How to run
1. Open a terminal in this folder.
2. Start the API server:
   - Windows PowerShell:
     - Optional one-time: python -m venv .venv; .venv\Scripts\Activate; pip install flask flask-cors scikit-learn numpy
     - Run: python .\unified_api_server.py
3. Open the pages directly in your browser from this folder (double-click the HTML files), or serve them via a simple static server if you prefer.

The pages call the API at http://localhost:5000. Ensure the server is running before interacting with the UI.

## Main pages
- role_select.html — entry page to pick Admin or Customer
- admin_login.html — admin login
- admininterface.html — admin dashboard
- inventory.html — live inventory view (DB-backed)
- forecasting.html — demand forecasting charts (Random Forest ML predictions)
- procurement.html — recommendations, approval, and PO cart flow
- customer_login.html — customer login
- customerinterface.html — storefront with persistent cart and checkout

## Notes
- The backend auto-detects the database in this same folder (employees.db). No extra path config required.
- If you need to reset the data, replace employees.db with a fresh copy from your source.
