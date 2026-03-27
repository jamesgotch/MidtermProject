# MidtermProject

Simple FastAPI dashboard and updater for the Colorado Springs police blotter.

## Install Dependencies

```bash
cd /workspaces/MidtermProject && /workspaces/MidtermProject/.venv/bin/pip install -r requirements.txt
```

## Run Files

### Run `main.py`

Starts the FastAPI dashboard.

```bash
fastapi dev main.py
```

### Run `update.py`

Scrapes fresh data, merges in only new incidents, and updates matching records without duplicating existing ones.

```bash
python update.py
```

### Run `read.py`

Prints quick summary counts in the terminal.

```bash
python read.py
```
