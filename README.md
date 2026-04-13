# MidtermProject

Simple FastAPI dashboard and updater for the Colorado Springs police blotter.

The dashboard now includes a filtered incident map below the list and detail panels. The map updates from the active filters and offers ArcGIS Streets, ArcGIS Satellite, and ArcGIS Topographic basemaps.

Map controls now include points, heatmap, combined view, and marker clustering, plus marker shape, color, and size controls. You can also overlay nearby places such as restaurants, parks, hotels, tourist spots, and hospitals in the current map view. Clicking a mapped event updates the incident details panel.

## Install Dependencies

```bash
cd /workspaces/MidtermProject && python3 -m pip install --user -r requirements.txt
```

`fastapi[standard]` installs the `fastapi` command used below, so you do not need to activate `.venv` first.

The map uses Leaflet plus public ArcGIS basemap and geocoding services, so an internet connection is required for the map tiles and backend geocoding runs. Coordinates are stored in SQLite so the browser no longer has to geocode incidents on each load.

## Run Files

### Run `main.py`

Starts the FastAPI dashboard.

```bash
fastapi dev main.py
```

### Run `update.py`

Scrapes fresh data, merges in only new incidents, and updates matching records without duplicating existing ones.

```bash
python3 update.py
```

### Run `read.py`

Prints quick summary counts in the terminal.

```bash
python3 read.py
```
