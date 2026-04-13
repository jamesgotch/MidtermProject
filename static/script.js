const MAP_DEFAULT_CENTER = [38.8339, -104.8214];
const MAP_DEFAULT_ZOOM = 11;
const OVERPASS_API_URL = "https://overpass-api.de/api/interpreter";

const basemapDefinitions = {
	"arcgis-streets": {
		url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
		options: {
			attribution: "&copy; Esri",
			maxZoom: 19,
		},
	},
	"arcgis-satellite": {
		url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
		options: {
			attribution: "&copy; Esri",
			maxZoom: 19,
		},
	},
	"arcgis-topo": {
		url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
		options: {
			attribution: "&copy; Esri",
			maxZoom: 19,
		},
	},
};

const poiCategoryDefinitions = {
	restaurants: {
		label: "Restaurants",
		color: "#d96d3b",
		filters: ['["amenity"~"restaurant|fast_food"]'],
	},
	cafes: {
		label: "Cafes",
		color: "#a16d4d",
		filters: ['["amenity"="cafe"]'],
	},
	hotels: {
		label: "Hotels",
		color: "#4f86c6",
		filters: ['["tourism"~"hotel|motel|guest_house"]'],
	},
	tourism: {
		label: "Tourist Spots",
		color: "#9c6644",
		filters: ['["tourism"~"attraction|museum|viewpoint|artwork|zoo|theme_park"]'],
	},
	parks: {
		label: "Parks",
		color: "#5f9f69",
		filters: ['["leisure"~"park|nature_reserve"]'],
	},
	hospitals: {
		label: "Hospitals",
		color: "#b63c5a",
		filters: ['["amenity"="hospital"]'],
	},
};

const state = {
	incidents: [],
	filtered: [],
	visible: [],
	selectedId: null,
	pageSize: "10",
	sortMode: "newest",
	selectedDivisions: [],
	selectedTitles: [],
	map: null,
	pointLayer: null,
	heatLayer: null,
	clusterLayer: null,
	poiLayer: null,
	labelsOverlay: null,
	mapLayers: {},
	activeBasemap: "arcgis-streets",
	mapDisplayMode: "points",
	satelliteLabelsEnabled: false,
	markerShape: "circle",
	markerColor: "#0f8b8d",
	markerSize: 18,
	mapSize: "tall",
	selectedPoiCategories: [],
	poiCache: new Map(),
	poiRefreshToken: 0,
};

const elements = {
	globalSearch: document.getElementById("globalSearch"),
	recordIdSearch: document.getElementById("recordIdSearch"),
	dateFilterMode: document.getElementById("dateFilterMode"),
	dateSearch: document.getElementById("dateSearch"),
	timeFilterGroup: document.getElementById("timeFilterGroup"),
	timeFilterMode: document.getElementById("timeFilterMode"),
	timeSearch: document.getElementById("timeSearch"),
	timeSearchEnd: document.getElementById("timeSearchEnd"),
	divisionFilter: document.getElementById("divisionFilter"),
	divisionFilterStack: document.getElementById("divisionFilterStack"),
	titleFilter: document.getElementById("titleFilter"),
	titleFilterStack: document.getElementById("titleFilterStack"),
	locationSearch: document.getElementById("locationSearch"),
	pageSizeSelect: document.getElementById("pageSizeSelect"),
	sortSelect: document.getElementById("sortSelect"),
	updateButton: document.getElementById("updateButton"),
	exportButton: document.getElementById("exportButton"),
	resetButton: document.getElementById("resetButton"),
	resultSummary: document.getElementById("resultSummary"),
	activeFilters: document.getElementById("activeFilters"),
	totalCount: document.getElementById("totalCount"),
	filteredCount: document.getElementById("filteredCount"),
	topDivision: document.getElementById("topDivision"),
	topTitle: document.getElementById("topTitle"),
	heroTotalCount: document.getElementById("heroTotalCount"),
	heroVisibleCount: document.getElementById("heroVisibleCount"),
	tableBody: document.getElementById("incidentTableBody"),
	detailContent: document.getElementById("detailContent"),
	detailHint: document.getElementById("detailHint"),
	loadingState: document.getElementById("loadingState"),
	basemapSelect: document.getElementById("basemapSelect"),
	poiCategorySelect: document.getElementById("poiCategorySelect"),
	poiFilterStack: document.getElementById("poiFilterStack"),
	mapDisplayMode: document.getElementById("mapDisplayMode"),
	mapSizeSelect: document.getElementById("mapSizeSelect"),
	markerShapeSelect: document.getElementById("markerShapeSelect"),
	markerColorInput: document.getElementById("markerColorInput"),
	markerSizeInput: document.getElementById("markerSizeInput"),
	markerSizeValue: document.getElementById("markerSizeValue"),
	satelliteLabelsToggle: document.getElementById("satelliteLabelsToggle"),
	mapStatus: document.getElementById("mapStatus"),
	poiStatus: document.getElementById("poiStatus"),
	mapContainer: document.getElementById("incidentMap"),
};

function normalize(value) {
	return String(value || "").trim().toLowerCase();
}

function escapeHtml(value) {
	return String(value || "")
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#39;");
}

function buildSearchText(incident) {
	return normalize([
		incident.record_id,
		incident.incident_date,
		incident.time,
		incident.division,
		incident.title,
		incident.location,
		incident.summary,
		incident.pd_contact_number,
	].join(" | "));
}

function parseIncidentDate(value) {
	const raw = String(value || "").replace(/^[A-Za-z]+,\s*/, "").trim();
	const parsed = Date.parse(raw);
	return Number.isNaN(parsed) ? 0 : parsed;
}

function toDateInputValue(timestamp) {
	if (!timestamp) {
		return "";
	}

	const date = new Date(timestamp);
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const day = String(date.getDate()).padStart(2, "0");
	return `${year}-${month}-${day}`;
}

function parseIncidentTime(value) {
	const match = String(value || "").trim().match(/^(\d{1,2}):(\d{2})(?:\s*([AP]M))?$/i);
	if (!match) {
		return null;
	}

	let hours = Number.parseInt(match[1], 10);
	const minutes = Number.parseInt(match[2], 10);
	const meridiem = match[3]?.toLowerCase();

	if (meridiem === "pm" && hours < 12) {
		hours += 12;
	}

	if (meridiem === "am" && hours === 12) {
		hours = 0;
	}

	if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
		return null;
	}

	return (hours * 60) + minutes;
}

function parseCoordinate(value) {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function sortIncidentsNewestFirst(incidents) {
	return [...incidents].sort((left, right) => parseIncidentDate(right.incident_date) - parseIncidentDate(left.incident_date));
}

function sortIncidents(items) {
	const incidents = [...items];

	if (state.sortMode === "oldest") {
		return incidents.sort((left, right) => parseIncidentDate(left.incident_date) - parseIncidentDate(right.incident_date));
	}

	if (state.sortMode === "title") {
		return incidents.sort((left, right) => normalize(left.title).localeCompare(normalize(right.title)));
	}

	if (state.sortMode === "division") {
		return incidents.sort((left, right) => normalize(left.division).localeCompare(normalize(right.division)));
	}

	if (state.sortMode === "record_id") {
		return incidents.sort((left, right) => normalize(left.record_id).localeCompare(normalize(right.record_id), undefined, { numeric: true }));
	}

	return incidents.sort((left, right) => parseIncidentDate(right.incident_date) - parseIncidentDate(left.incident_date));
}

function uniqueValues(items, key) {
	return [...new Set(items.map((item) => item[key]).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function fillSelect(selectElement, values, defaultLabel) {
	selectElement.innerHTML = "";

	const firstOption = document.createElement("option");
	firstOption.value = "";
	firstOption.textContent = defaultLabel;
	selectElement.appendChild(firstOption);

	values.forEach((value) => {
		const option = document.createElement("option");
		option.value = value;
		option.textContent = value;
		selectElement.appendChild(option);
	});
}

function currentFilters() {
	return {
		global: normalize(elements.globalSearch.value),
		recordId: normalize(elements.recordIdSearch.value),
		dateMode: elements.dateFilterMode.value,
		date: elements.dateSearch.value,
		timeMode: elements.timeFilterMode.value,
		time: elements.timeSearch.value,
		timeEnd: elements.timeSearchEnd.value,
		divisions: state.selectedDivisions.map(normalize),
		titles: state.selectedTitles.map(normalize),
		location: normalize(elements.locationSearch.value),
	};
}

function renderStackedFilterList(container, values, filterName) {
	container.innerHTML = values
		.map((value) => `<button class="stacked-filter-chip" type="button" data-filter-name="${escapeHtml(filterName)}" data-filter-value="${escapeHtml(value)}">${escapeHtml(value)} <span aria-hidden="true">x</span></button>`)
		.join("");

	container.querySelectorAll(".stacked-filter-chip").forEach((button) => {
		button.addEventListener("click", () => {
			clearFilter(`${button.dataset.filterName}::${button.dataset.filterValue}`);
		});
	});
}

function renderStackedFilters() {
	renderStackedFilterList(elements.divisionFilterStack, state.selectedDivisions, "Division");
	renderStackedFilterList(elements.titleFilterStack, state.selectedTitles, "Title");
}

function renderPoiFilterStack() {
	elements.poiFilterStack.innerHTML = state.selectedPoiCategories
		.map((categoryKey) => {
			const category = poiCategoryDefinitions[categoryKey];
			if (!category) {
				return "";
			}

			return `<button class="stacked-filter-chip" type="button" data-poi-category="${escapeHtml(categoryKey)}">${escapeHtml(category.label)} <span aria-hidden="true">x</span></button>`;
		})
		.join("");

	elements.poiFilterStack.querySelectorAll("[data-poi-category]").forEach((button) => {
		button.addEventListener("click", () => {
			state.selectedPoiCategories = state.selectedPoiCategories.filter((value) => value !== button.dataset.poiCategory);
			renderPoiFilterStack();
			refreshNearbyPlaces();
		});
	});
}

function addStackedFilter(collectionName, value) {
	const cleanedValue = String(value || "").trim();
	if (!cleanedValue) {
		return;
	}

	if (!state[collectionName].includes(cleanedValue)) {
		state[collectionName].push(cleanedValue);
	}
}

function addPoiCategory(value) {
	const cleanedValue = String(value || "").trim();
	if (!cleanedValue || !poiCategoryDefinitions[cleanedValue]) {
		return;
	}

	if (!state.selectedPoiCategories.includes(cleanedValue)) {
		state.selectedPoiCategories.push(cleanedValue);
	}

	renderPoiFilterStack();
	refreshNearbyPlaces();
}

function updateTimeFilterMode() {
	const mode = elements.timeFilterMode.value;
	elements.timeFilterGroup.dataset.mode = mode;
	const showEndTime = mode === "between";
	elements.timeSearchEnd.disabled = !showEndTime;
	if (!showEndTime) {
		elements.timeSearchEnd.value = "";
	}
}

function getVisibleIncidents() {
	if (state.pageSize === "all") {
		return [...state.filtered];
	}

	const limit = Number.parseInt(state.pageSize, 10);
	if (Number.isNaN(limit) || limit <= 0) {
		return [...state.filtered];
	}

	return state.filtered.slice(0, limit);
}

function topLabel(items, key) {
	if (!items.length) {
		return "-";
	}

	const counts = new Map();
	items.forEach((item) => {
		const value = item[key] || "Unknown";
		counts.set(value, (counts.get(value) || 0) + 1);
	});

	return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

function selectedIncident() {
	return state.filtered.find((incident) => incident.record_id === state.selectedId)
		|| state.incidents.find((incident) => incident.record_id === state.selectedId)
		|| null;
}

function applyFilters() {
	const filters = currentFilters();
	state.filtered = state.incidents.filter((incident) => {
		const incidentDateValue = toDateInputValue(parseIncidentDate(incident.incident_date));
		const incidentTimeValue = parseIncidentTime(incident.time);

		if (filters.global && !buildSearchText(incident).includes(filters.global)) {
			return false;
		}
		if (filters.recordId && !normalize(incident.record_id).includes(filters.recordId)) {
			return false;
		}
		if (filters.date) {
			if (!incidentDateValue) {
				return false;
			}

			if (filters.dateMode === "on" && incidentDateValue !== filters.date) {
				return false;
			}

			if (filters.dateMode === "after" && incidentDateValue <= filters.date) {
				return false;
			}

			if (filters.dateMode === "before" && incidentDateValue >= filters.date) {
				return false;
			}
		}
		if (filters.time) {
			const startTimeValue = parseIncidentTime(filters.time);
			if (incidentTimeValue === null || startTimeValue === null) {
				return false;
			}

			if (filters.timeMode === "at" && incidentTimeValue !== startTimeValue) {
				return false;
			}

			if (filters.timeMode === "after" && incidentTimeValue <= startTimeValue) {
				return false;
			}

			if (filters.timeMode === "before" && incidentTimeValue >= startTimeValue) {
				return false;
			}

			if (filters.timeMode === "between") {
				const endTimeValue = parseIncidentTime(filters.timeEnd);
				if (endTimeValue === null) {
					return false;
				}

				const lowerBound = Math.min(startTimeValue, endTimeValue);
				const upperBound = Math.max(startTimeValue, endTimeValue);
				if (incidentTimeValue < lowerBound || incidentTimeValue > upperBound) {
					return false;
				}
			}
		}
		if (filters.divisions.length && !filters.divisions.includes(normalize(incident.division))) {
			return false;
		}
		if (filters.titles.length && !filters.titles.includes(normalize(incident.title))) {
			return false;
		}
		if (filters.location && !normalize(incident.location).includes(filters.location)) {
			return false;
		}
		return true;
	});

	state.filtered = sortIncidents(state.filtered);
	state.visible = getVisibleIncidents();

	if (!state.filtered.some((incident) => incident.record_id === state.selectedId)) {
		state.selectedId = state.filtered[0]?.record_id || null;
	}

	renderSummary();
	renderTable();
	renderDetails();
	renderStackedFilters();
	refreshMap();
}

function renderSummary() {
	const total = state.incidents.length;
	const filtered = state.filtered.length;
	const visible = state.visible.length;

	elements.totalCount.textContent = total;
	elements.filteredCount.textContent = filtered;
	elements.heroTotalCount.textContent = total;
	elements.heroVisibleCount.textContent = filtered;
	elements.topDivision.textContent = topLabel(state.filtered, "division");
	elements.topTitle.textContent = topLabel(state.filtered, "title");
	elements.resultSummary.textContent = `${visible} of ${filtered} result${filtered === 1 ? "" : "s"} shown`;
	elements.loadingState.textContent = filtered ? `Showing ${visible} of ${filtered} incidents` : "No incidents match your filters";
	renderActiveFilters();
}

function renderActiveFilters() {
	const filters = [
		["Search", elements.globalSearch.value],
		["Record ID", elements.recordIdSearch.value],
		["Location", elements.locationSearch.value],
	];

	if (elements.dateSearch.value) {
		filters.push(["Date", `${elements.dateFilterMode.value} ${elements.dateSearch.value}`]);
	}

	if (elements.timeSearch.value) {
		const timeLabel = elements.timeFilterMode.value === "between"
			? `between ${elements.timeSearch.value} and ${elements.timeSearchEnd.value || "?"}`
			: `${elements.timeFilterMode.value} ${elements.timeSearch.value}`;
		filters.push(["Time", timeLabel]);
	}

	state.selectedDivisions.forEach((value) => {
		filters.push(["Division", value]);
	});

	state.selectedTitles.forEach((value) => {
		filters.push(["Title", value]);
	});

	elements.activeFilters.innerHTML = filters
		.filter(([, value]) => String(value || "").trim())
		.map(([label, value]) => `<button class="filter-tag" type="button" data-filter="${escapeHtml(label)}">${escapeHtml(label)}: ${escapeHtml(value)}</button>`)
		.join("");

	elements.activeFilters.querySelectorAll(".filter-tag").forEach((button) => {
		button.addEventListener("click", () => clearFilter(button.dataset.filter));
	});
}

function clearFilter(label) {
	const [filterName, filterValue] = String(label || "").split("::");

	if (filterName === "Division" && filterValue) {
		state.selectedDivisions = state.selectedDivisions.filter((value) => value !== filterValue);
		applyFilters();
		return;
	}

	if (filterName === "Title" && filterValue) {
		state.selectedTitles = state.selectedTitles.filter((value) => value !== filterValue);
		applyFilters();
		return;
	}

	if (label === "Search") elements.globalSearch.value = "";
	if (label === "Record ID") elements.recordIdSearch.value = "";
	if (label === "Date") {
		elements.dateFilterMode.value = "on";
		elements.dateSearch.value = "";
	}
	if (label === "Time") {
		elements.timeFilterMode.value = "at";
		elements.timeSearch.value = "";
		elements.timeSearchEnd.value = "";
		updateTimeFilterMode();
	}
	if (label === "Location") elements.locationSearch.value = "";
	applyFilters();
}

function selectIncident(recordId, options = {}) {
	state.selectedId = recordId;
	renderTable();
	renderDetails();
	refreshMap(options);
}

function renderTable() {
	elements.tableBody.innerHTML = "";

	if (!state.visible.length) {
		const row = document.createElement("tr");
		const cell = document.createElement("td");
		cell.colSpan = 6;
		cell.innerHTML = '<div class="table-empty">No incidents matched the current filters.</div>';
		row.appendChild(cell);
		elements.tableBody.appendChild(row);
		return;
	}

	state.visible.forEach((incident) => {
		const row = document.createElement("tr");
		if (incident.record_id === state.selectedId) {
			row.classList.add("is-active");
		}

		row.innerHTML = `
			<td><span class="pill">${escapeHtml(incident.record_id || "N/A")}</span></td>
			<td>${escapeHtml(incident.incident_date || "N/A")}</td>
			<td>${escapeHtml(incident.time || "N/A")}</td>
			<td>${escapeHtml(incident.division || "N/A")}</td>
			<td>${escapeHtml(incident.title || "N/A")}</td>
			<td>${escapeHtml(incident.location || "N/A")}</td>
		`;

		row.addEventListener("click", () => {
			selectIncident(incident.record_id, { preserveView: true, focusSelected: true });
		});

		elements.tableBody.appendChild(row);
	});
}

function renderDetails() {
	const incident = selectedIncident();

	if (!incident) {
		elements.detailHint.textContent = "Select an incident row to view more information.";
		elements.detailContent.className = "detail-content empty-state";
		elements.detailContent.textContent = "Pick a record from the table to see its full summary, contact details, and location.";
		return;
	}

	elements.detailHint.textContent = `Record ${incident.record_id || "N/A"}`;
	elements.detailContent.className = "detail-content fade-in";
	elements.detailContent.innerHTML = `
		<div class="detail-grid">
			<div class="detail-item"><span>Record ID</span><strong>${escapeHtml(incident.record_id || "N/A")}</strong></div>
			<div class="detail-item"><span>Date</span><strong>${escapeHtml(incident.incident_date || "N/A")}</strong></div>
			<div class="detail-item"><span>Time</span><strong>${escapeHtml(incident.time || "N/A")}</strong></div>
			<div class="detail-item"><span>Division</span><strong>${escapeHtml(incident.division || "N/A")}</strong></div>
			<div class="detail-item"><span>Title</span><strong>${escapeHtml(incident.title || "N/A")}</strong></div>
			<div class="detail-item"><span>Location</span><strong>${escapeHtml(incident.location || "N/A")}</strong></div>
			<div class="detail-item"><span>Adults Arrested</span><strong>${escapeHtml(incident.adults_arrested || "N/A")}</strong></div>
			<div class="detail-item"><span>PD Contact & Number</span><strong>${escapeHtml(incident.pd_contact_number || "N/A")}</strong></div>
		</div>
		<div class="detail-summary">
			<strong>Summary</strong>
			<p>${escapeHtml(incident.summary || "No summary provided.")}</p>
		</div>
	`;
}

function resetFilters() {
	elements.globalSearch.value = "";
	elements.recordIdSearch.value = "";
	elements.dateSearch.value = "";
	elements.timeFilterMode.value = "at";
	elements.timeSearch.value = "";
	elements.timeSearchEnd.value = "";
	elements.divisionFilter.value = "";
	elements.titleFilter.value = "";
	elements.locationSearch.value = "";
	elements.pageSizeSelect.value = "10";
	elements.sortSelect.value = "newest";
	state.pageSize = "10";
	state.sortMode = "newest";
	state.selectedDivisions = [];
	state.selectedTitles = [];
	updateTimeFilterMode();
	applyFilters();
}

function exportFilteredResults() {
	const headers = [
		"Record ID",
		"Incident Date",
		"Time",
		"Division",
		"Title",
		"Location",
		"Summary",
		"Adults Arrested",
		"PD Contact & Number",
	];

	const rows = state.filtered.map((incident) => [
		incident.record_id || "",
		incident.incident_date || "",
		incident.time || "",
		incident.division || "",
		incident.title || "",
		incident.location || "",
		incident.summary || "",
		incident.adults_arrested || "",
		incident.pd_contact_number || "",
	]);

	const csv = [headers, ...rows]
		.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
		.join("\n");

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = "filtered-incidents.csv";
	document.body.appendChild(link);
	link.click();
	link.remove();
	URL.revokeObjectURL(url);
}

function satelliteLabelsAvailable() {
	return state.activeBasemap === "arcgis-satellite";
}

function hexToRgba(hex, alpha) {
	const clean = String(hex || "").replace("#", "");
	if (clean.length !== 6) {
		return `rgba(15, 139, 141, ${alpha})`;
	}

	const red = Number.parseInt(clean.slice(0, 2), 16);
	const green = Number.parseInt(clean.slice(2, 4), 16);
	const blue = Number.parseInt(clean.slice(4, 6), 16);
	return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function ensureMap() {
	if (state.map) {
		return true;
	}

	if (!elements.mapContainer || typeof window.L === "undefined") {
		elements.mapStatus.textContent = "Map library failed to load.";
		return false;
	}

	state.map = window.L.map(elements.mapContainer, {
		center: MAP_DEFAULT_CENTER,
		zoom: MAP_DEFAULT_ZOOM,
		preferCanvas: true,
	});

	state.mapLayers = Object.fromEntries(
		Object.entries(basemapDefinitions).map(([key, definition]) => [key, window.L.tileLayer(definition.url, definition.options)]),
	);

	state.labelsOverlay = window.L.tileLayer(
		"https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
		{
			attribution: "&copy; Esri",
			maxZoom: 19,
			opacity: 0.9,
		},
	);

	state.pointLayer = window.L.layerGroup().addTo(state.map);
	state.heatLayer = window.L.heatLayer([], {
		radius: 28,
		blur: 22,
		maxZoom: 16,
		gradient: {
			0.2: "#4cc9f0",
			0.45: "#0f8b8d",
			0.7: "#f4a261",
			1.0: "#d96d3b",
		},
	});
	state.clusterLayer = window.L.markerClusterGroup({
		showCoverageOnHover: false,
		spiderfyOnMaxZoom: true,
		maxClusterRadius: 56,
		iconCreateFunction(cluster) {
			const count = cluster.getChildCount();
			const size = count < 10 ? 42 : count < 30 ? 50 : 58;
			const html = `<div class="cluster-badge" style="--cluster-size:${size}px; --cluster-color:${escapeHtml(state.markerColor)}; --cluster-color-soft:${escapeHtml(hexToRgba(state.markerColor, 0.22))};">${count}</div>`;
			return window.L.divIcon({
				html,
				className: "cluster-badge-shell",
				iconSize: window.L.point(size, size),
			});
		},
	});
	state.poiLayer = window.L.layerGroup().addTo(state.map);

	setBasemap(state.activeBasemap);
	updateSatelliteLabelsAvailability();
	state.map.on("moveend", () => {
		refreshNearbyPlaces();
	});

	window.setTimeout(() => {
		state.map?.invalidateSize();
	}, 0);

	return true;
}

function setBasemap(key) {
	if (!ensureMap()) {
		return;
	}

	const nextLayer = state.mapLayers[key] || state.mapLayers["arcgis-streets"];
	if (!nextLayer) {
		return;
	}

	if (state.activeBasemap && state.mapLayers[state.activeBasemap]) {
		state.map.removeLayer(state.mapLayers[state.activeBasemap]);
	}

	nextLayer.addTo(state.map);
	state.activeBasemap = key;
	elements.basemapSelect.value = key;
	updateSatelliteLabelsAvailability();
	applySatelliteLabelsOverlay();
}

function updateSatelliteLabelsAvailability() {
	const available = satelliteLabelsAvailable();
	elements.satelliteLabelsToggle.disabled = !available;
	if (!available) {
		state.satelliteLabelsEnabled = false;
		elements.satelliteLabelsToggle.checked = false;
	}
}

function applySatelliteLabelsOverlay() {
	if (!ensureMap() || !state.labelsOverlay) {
		return;
	}

	const shouldShow = satelliteLabelsAvailable() && state.satelliteLabelsEnabled;
	if (shouldShow) {
		state.labelsOverlay.addTo(state.map);
		return;
	}

	state.map.removeLayer(state.labelsOverlay);
}

function applyMapSize() {
	if (!elements.mapContainer) {
		return;
	}

	elements.mapContainer.dataset.size = state.mapSize;
	state.map?.invalidateSize();
}

function poiBoundsKey(bounds) {
	const south = bounds.getSouth().toFixed(3);
	const west = bounds.getWest().toFixed(3);
	const north = bounds.getNorth().toFixed(3);
	const east = bounds.getEast().toFixed(3);
	return `${south},${west},${north},${east}`;
}

function buildPoiQuery(categoryKey, bounds) {
	const category = poiCategoryDefinitions[categoryKey];
	if (!category) {
		return "";
	}

	const bbox = `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`;
	const selectors = category.filters.flatMap((filter) => [
		`node${filter}(${bbox});`,
		`way${filter}(${bbox});`,
		`relation${filter}(${bbox});`,
	]);

	return `[out:json][timeout:18];(${selectors.join("")});out center;`;
}

function poiPopupContent(place, category) {
	return `
		<div class="map-popup">
			<strong>${escapeHtml(place.name || category.label)}</strong>
			<div>${escapeHtml(category.label)}</div>
			<div>${escapeHtml(place.address || "No address available")}</div>
		</div>
	`;
}

async function fetchNearbyPlacesForCategory(categoryKey, bounds) {
	const category = poiCategoryDefinitions[categoryKey];
	if (!category) {
		return [];
	}

	const cacheKey = `${categoryKey}|${poiBoundsKey(bounds)}`;
	if (state.poiCache.has(cacheKey)) {
		return state.poiCache.get(cacheKey);
	}

	const response = await fetch(OVERPASS_API_URL, {
		method: "POST",
		headers: {
			"Content-Type": "text/plain;charset=UTF-8",
		},
		body: buildPoiQuery(categoryKey, bounds),
	});

	if (!response.ok) {
		throw new Error(`Nearby places request failed: ${response.status}`);
	}

	const payload = await response.json();
	const places = (payload.elements || []).reduce((results, item) => {
		const latitude = item.lat ?? item.center?.lat;
		const longitude = item.lon ?? item.center?.lon;
		if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
			return results;
		}

		results.push({
			id: item.id,
			categoryKey,
			lat: latitude,
			lng: longitude,
			name: item.tags?.name || item.tags?.brand || category.label,
			address: [item.tags?.["addr:housenumber"], item.tags?.["addr:street"]].filter(Boolean).join(" "),
		});
		return results;
	}, []);

	state.poiCache.set(cacheKey, places);
	return places;
}

async function refreshNearbyPlaces() {
	if (!ensureMap() || !state.poiLayer) {
		return;
	}

	state.poiLayer.clearLayers();

	if (!state.selectedPoiCategories.length) {
		elements.poiStatus.textContent = "Nearby place overlays are off.";
		return;
	}

	const bounds = state.map.getBounds();
	const refreshToken = state.poiRefreshToken + 1;
	state.poiRefreshToken = refreshToken;
	const categoryCount = state.selectedPoiCategories.length;
	elements.poiStatus.textContent = `Loading ${categoryCount} nearby place layer${categoryCount === 1 ? "" : "s"}...`;

	try {
		const placeGroups = await Promise.all(state.selectedPoiCategories.map((categoryKey) => fetchNearbyPlacesForCategory(categoryKey, bounds)));
		if (refreshToken !== state.poiRefreshToken) {
			return;
		}

		let totalPlaces = 0;
		placeGroups.forEach((places, index) => {
			const categoryKey = state.selectedPoiCategories[index];
			const category = poiCategoryDefinitions[categoryKey];
			if (!category) {
				return;
			}

			places.forEach((place) => {
				totalPlaces += 1;
				window.L.circleMarker([place.lat, place.lng], {
					radius: 6,
					color: category.color,
					fillColor: category.color,
					fillOpacity: 0.82,
					weight: 2,
					opacity: 0.95,
				}).bindPopup(poiPopupContent(place, category)).addTo(state.poiLayer);
			});
		});

		elements.poiStatus.textContent = totalPlaces
			? `${totalPlaces} nearby location${totalPlaces === 1 ? "" : "s"} shown across ${categoryCount} selected layer${categoryCount === 1 ? "" : "s"}.`
			: `No nearby locations found in the current map view for the selected ${categoryCount === 1 ? "layer" : "layers"}.`;
	} catch (error) {
		if (refreshToken !== state.poiRefreshToken) {
			return;
		}

		elements.poiStatus.textContent = `Nearby places could not load. ${error.message}`;
	}
}

function mappedIncidentEntries(incidents) {
	return incidents.reduce((entries, incident) => {
		const latitude = parseCoordinate(incident.latitude);
		const longitude = parseCoordinate(incident.longitude);
		if (latitude === null || longitude === null) {
			return entries;
		}

		entries.push({
			incident,
			coordinates: {
				lat: latitude,
				lng: longitude,
				provider: incident.geocode_provider || "ArcGIS",
				label: incident.geocoded_query || incident.location || "",
			},
		});
		return entries;
	}, []);
}

function markerIconOptions(selected) {
	const baseSize = selected ? state.markerSize + 6 : state.markerSize;
	const iconSize = state.markerShape === "triangle"
		? window.L.point(baseSize + 6, baseSize + 6)
		: window.L.point(baseSize + 10, baseSize + 10);

	return {
		iconSize,
		iconAnchor: window.L.point(iconSize.x / 2, iconSize.y / 2),
		popupAnchor: window.L.point(0, -Math.round(iconSize.y / 2)),
	};
}

function createMarkerIcon(selected) {
	const classes = ["map-pin", `map-pin-${state.markerShape}`];
	if (selected) {
		classes.push("is-selected");
	}

	const iconOptions = markerIconOptions(selected);
	return window.L.divIcon({
		className: "map-pin-icon",
		html: `<span class="${classes.join(" ")}" style="--marker-size:${state.markerSize}px; --marker-color:${escapeHtml(state.markerColor)};"></span>`,
		iconSize: iconOptions.iconSize,
		iconAnchor: iconOptions.iconAnchor,
		popupAnchor: iconOptions.popupAnchor,
	});
}

function incidentPopupContent(incident, coordinates) {
	return `
		<div class="map-popup">
			<strong>${escapeHtml(incident.title || "Incident")}</strong>
			<div>${escapeHtml(incident.location || "No location")}</div>
			<div>${escapeHtml(incident.incident_date || "No date")} at ${escapeHtml(incident.time || "N/A")}</div>
			<div>Record ${escapeHtml(incident.record_id || "N/A")}</div>
			<div class="map-popup-provider">Geocoded via ${escapeHtml(coordinates.provider || "ArcGIS")}</div>
		</div>
	`;
}

function clearVisualizationLayers() {
	if (state.pointLayer) {
		state.pointLayer.clearLayers();
	}

	if (state.clusterLayer) {
		state.clusterLayer.clearLayers();
		if (state.map.hasLayer(state.clusterLayer)) {
			state.map.removeLayer(state.clusterLayer);
		}
	}

	if (state.heatLayer && state.map.hasLayer(state.heatLayer)) {
		state.map.removeLayer(state.heatLayer);
	}
}

function buildIncidentMarker(entry) {
	const { incident, coordinates } = entry;
	const selected = incident.record_id === state.selectedId;
	const marker = window.L.marker([coordinates.lat, coordinates.lng], {
		icon: createMarkerIcon(selected),
		keyboard: true,
		title: incident.title || incident.record_id || "Incident",
	});

	marker.bindPopup(incidentPopupContent(incident, coordinates));
	marker.on("click", () => {
		selectIncident(incident.record_id, { preserveView: true, focusSelected: true });
	});

	return marker;
}

function renderPointMarkers(entries, useClusters) {
	let selectedMarker = null;
	const target = useClusters ? state.clusterLayer : state.pointLayer;

	entries.forEach((entry) => {
		const marker = buildIncidentMarker(entry);
		marker.addTo(target);
		if (entry.incident.record_id === state.selectedId) {
			selectedMarker = marker;
		}
	});

	if (useClusters && !state.map.hasLayer(state.clusterLayer)) {
		state.clusterLayer.addTo(state.map);
	}

	return selectedMarker;
}

function renderHeatLayer(entries) {
	if (!state.heatLayer) {
		return;
	}

	state.heatLayer.setLatLngs(entries.map(({ coordinates }) => [coordinates.lat, coordinates.lng, 0.8]));
	state.heatLayer.addTo(state.map);
}

function focusMarker(marker, useClusters) {
	if (!marker) {
		return;
	}

	if (useClusters && state.clusterLayer) {
		state.clusterLayer.zoomToShowLayer(marker, () => {
			state.map.setView(marker.getLatLng(), Math.max(state.map.getZoom(), 13));
			marker.openPopup();
		});
		return;
	}

	state.map.flyTo(marker.getLatLng(), Math.max(state.map.getZoom(), 13), { duration: 0.45 });
	marker.openPopup();
}

function refreshMap(options = {}) {
	if (!ensureMap()) {
		return;
	}

	clearVisualizationLayers();

	const entries = mappedIncidentEntries(state.filtered);
	const bounds = entries.map(({ coordinates }) => [coordinates.lat, coordinates.lng]);
	const mappedCount = entries.length;
	const unresolvedCount = Math.max(0, state.filtered.length - mappedCount);

	if (!mappedCount) {
		state.map.setView(MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM);
		elements.mapStatus.textContent = state.filtered.length
			? "Filtered incidents exist, but none have stored map coordinates yet."
			: "No incidents match the current filters.";
		refreshNearbyPlaces();
		return;
	}

	let selectedMarker = null;
	if (state.mapDisplayMode === "points") {
		selectedMarker = renderPointMarkers(entries, false);
	} else if (state.mapDisplayMode === "heatmap") {
		renderHeatLayer(entries);
	} else if (state.mapDisplayMode === "combined") {
		selectedMarker = renderPointMarkers(entries, false);
		renderHeatLayer(entries);
	} else if (state.mapDisplayMode === "clusters") {
		selectedMarker = renderPointMarkers(entries, true);
	}

	if (options.focusSelected && selectedMarker) {
		focusMarker(selectedMarker, state.mapDisplayMode === "clusters");
	} else if (!options.preserveView) {
		state.map.fitBounds(bounds, {
			padding: [32, 32],
			maxZoom: 14,
		});
	}

	const modeLabel = state.mapDisplayMode === "combined"
		? "points + heatmap"
		: state.mapDisplayMode === "clusters"
			? "marker clusters"
			: state.mapDisplayMode;
	const labelsNote = satelliteLabelsAvailable() && state.satelliteLabelsEnabled ? " with satellite labels" : "";
	elements.mapStatus.textContent = unresolvedCount
		? `${mappedCount} filtered incident${mappedCount === 1 ? "" : "s"} shown as ${modeLabel}${labelsNote}; ${unresolvedCount} still do not have stored coordinates.`
		: `${mappedCount} filtered incident${mappedCount === 1 ? "" : "s"} shown as ${modeLabel}${labelsNote}.`;
	refreshNearbyPlaces();
}

function wireEvents() {
	[
		elements.globalSearch,
		elements.recordIdSearch,
		elements.locationSearch,
	].forEach((element) => {
		element.addEventListener("input", applyFilters);
		element.addEventListener("change", applyFilters);
	});

	elements.dateFilterMode.addEventListener("change", applyFilters);
	elements.dateSearch.addEventListener("input", applyFilters);
	elements.dateSearch.addEventListener("change", applyFilters);
	elements.timeFilterMode.addEventListener("change", () => {
		updateTimeFilterMode();
		applyFilters();
	});
	elements.timeSearch.addEventListener("input", applyFilters);
	elements.timeSearch.addEventListener("change", applyFilters);
	elements.timeSearchEnd.addEventListener("input", applyFilters);
	elements.timeSearchEnd.addEventListener("change", applyFilters);

	elements.divisionFilter.addEventListener("change", () => {
		addStackedFilter("selectedDivisions", elements.divisionFilter.value);
		elements.divisionFilter.value = "";
		applyFilters();
	});

	elements.titleFilter.addEventListener("change", () => {
		addStackedFilter("selectedTitles", elements.titleFilter.value);
		elements.titleFilter.value = "";
		applyFilters();
	});

	elements.pageSizeSelect.addEventListener("change", () => {
		state.pageSize = elements.pageSizeSelect.value;
		state.visible = getVisibleIncidents();
		renderSummary();
		renderTable();
		renderDetails();
	});

	elements.sortSelect.addEventListener("change", () => {
		state.sortMode = elements.sortSelect.value;
		applyFilters();
	});

	elements.basemapSelect.addEventListener("change", () => {
		setBasemap(elements.basemapSelect.value);
		refreshMap({ preserveView: true });
	});

	elements.poiCategorySelect.addEventListener("change", () => {
		addPoiCategory(elements.poiCategorySelect.value);
		elements.poiCategorySelect.value = "";
	});

	elements.mapDisplayMode.addEventListener("change", () => {
		state.mapDisplayMode = elements.mapDisplayMode.value;
		refreshMap({ preserveView: true });
	});

	elements.mapSizeSelect.addEventListener("change", () => {
		state.mapSize = elements.mapSizeSelect.value;
		applyMapSize();
	});

	elements.markerShapeSelect.addEventListener("change", () => {
		state.markerShape = elements.markerShapeSelect.value;
		refreshMap({ preserveView: true });
	});

	elements.markerColorInput.addEventListener("input", () => {
		state.markerColor = elements.markerColorInput.value;
		refreshMap({ preserveView: true });
	});

	elements.markerSizeInput.addEventListener("input", () => {
		state.markerSize = Number(elements.markerSizeInput.value);
		elements.markerSizeValue.textContent = `${state.markerSize}px`;
		refreshMap({ preserveView: true });
	});

	elements.satelliteLabelsToggle.addEventListener("change", () => {
		state.satelliteLabelsEnabled = elements.satelliteLabelsToggle.checked;
		applySatelliteLabelsOverlay();
		refreshMap({ preserveView: true });
	});

	elements.updateButton.addEventListener("click", async () => {
		elements.updateButton.disabled = true;
		elements.loadingState.textContent = "Updating data... this can take a minute";

		try {
			const response = await fetch("/api/update", { method: "POST" });
			const payload = await response.json();

			if (!response.ok) {
				throw new Error(payload.detail || `Request failed: ${response.status}`);
			}

			await loadIncidents();
			elements.loadingState.textContent = `Update complete: ${payload.current_count} incidents saved (${payload.new_count} new, ${payload.geocoded_count} geocoded)`;
		} catch (error) {
			elements.loadingState.textContent = `Update failed: ${error.message}`;
		} finally {
			elements.updateButton.disabled = false;
		}
	});

	elements.exportButton.addEventListener("click", exportFilteredResults);
	elements.resetButton.addEventListener("click", resetFilters);

	document.addEventListener("keydown", (event) => {
		if (event.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "SELECT") {
			event.preventDefault();
			elements.globalSearch.focus();
		}
	});

	window.addEventListener("resize", () => {
		state.map?.invalidateSize();
	});
}

async function loadIncidents() {
	const response = await fetch("/api/incidents");
	if (!response.ok) {
		throw new Error(`Request failed: ${response.status}`);
	}

	const payload = await response.json();
	state.incidents = sortIncidentsNewestFirst(payload.incidents || []);
	state.filtered = sortIncidents([...state.incidents]);
	state.visible = getVisibleIncidents();
	state.selectedId = state.filtered[0]?.record_id || null;

	fillSelect(elements.divisionFilter, uniqueValues(state.incidents, "division"), "Add a division filter");
	fillSelect(elements.titleFilter, uniqueValues(state.incidents, "title"), "Add an incident type filter");

	renderSummary();
	renderTable();
	renderDetails();
	renderStackedFilters();
	renderPoiFilterStack();
	refreshMap();
}

async function startApp() {
	state.mapDisplayMode = elements.mapDisplayMode.value;
	state.mapSize = elements.mapSizeSelect.value;
	state.markerShape = elements.markerShapeSelect.value;
	state.markerColor = elements.markerColorInput.value;
	state.markerSize = Number(elements.markerSizeInput.value);
	elements.markerSizeValue.textContent = `${state.markerSize}px`;
	updateTimeFilterMode();
	renderPoiFilterStack();
	applyMapSize();

	wireEvents();

	try {
		await loadIncidents();
	} catch (error) {
		elements.loadingState.textContent = "Unable to load incident data";
		elements.resultSummary.textContent = "Data load failed";
		elements.detailContent.className = "detail-content empty-state";
		elements.detailContent.textContent = `The dashboard could not load incidents. ${error.message}`;
	}
}

startApp();
