HOW TO RUN — ShelfWare

This guide explains how to run ShelfWare locally for development and testing.
It assumes you have Python 3.10+ installed on Windows (the project was developed with Python 3.11+).

1) Prepare a virtual environment

Open PowerShell in the project root and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

Note: `requirements.txt` should contain at least Flask, flask-cors, numpy, scikit-learn. If you add packages, update the file.

3) Configure local database (optional)

This repository keeps data files out of Git by default. If you have a local SQLite database file (for example `employees.db`) place it in the `shelfware_bundle/` directory next to `unified_api_server.py`.

If you don't have a DB and just want to run the server, create an empty SQLite file named `employees.db` in `shelfware_bundle/`. The app will fail on some endpoints that expect tables; it's best to use the included DB (if you have it locally).

4) Start the API server

Run from the project root (this will run the Flask app defined in `shelfware_bundle/unified_api_server.py`):

```powershell
python .\shelfware_bundle\unified_api_server.py
```

You should see the server start and listen on `http://127.0.0.1:5000`.

5) Open the UI pages

The frontend is static HTML/CSS/JS files. For quick local testing you can open pages directly in your browser from the `shelfware_bundle/` or `UI/` folder.

Recommended pages to open in your browser:
- `shelfware_bundle/customerinterface.html` — storefront
- `shelfware_bundle/admininterface.html` — admin dashboard
- `shelfware_bundle/forecasting.html` — forecasting demo
- `shelfware_bundle/procurement.html` — procurement flow

Note: these pages call the API endpoints at `http://localhost:5000`. Keep the Flask server running while using the UI.

6) Common commands

- Restart server: Ctrl+C in the terminal where server is running, then run the `python` command again.
- Reset virtual environment: remove `.venv` and create a new one.

7) Troubleshooting

- "Server crashed with sqlite3.OperationalError: incomplete input" — ensure you've pulled the latest server code (we recently fixed a bug in the `/products` count SQL). If you still see it, paste the full traceback and I'll help debug.
- If HTML pages show no data, confirm the Flask server is running on port 5000 and that a readable `employees.db` exists in `shelfware_bundle/`.

8) Pushing to GitHub

- This project intentionally does not include local database or CSV exports. Before pushing, check `.gitignore` to confirm personal data/files are excluded.
- Commit code changes and push normally with `git add`, `git commit`, `git push`.

---

If you want, I can also provide a simple script to create a minimal SQLite DB with the required tables and a few sample rows to make the UI fully functional for demonstrations. Ask and I'll add it.
