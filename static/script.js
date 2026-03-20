const state = {
	incidents: [],
	filtered: [],
	visible: [],
	selectedId: null,
	pageSize: "10",
	sortMode: "newest",
};

const elements = {
	globalSearch: document.getElementById("globalSearch"),
	recordIdSearch: document.getElementById("recordIdSearch"),
	dateSearch: document.getElementById("dateSearch"),
	timeSearch: document.getElementById("timeSearch"),
	divisionFilter: document.getElementById("divisionFilter"),
	titleFilter: document.getElementById("titleFilter"),
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
		date: normalize(elements.dateSearch.value),
		time: normalize(elements.timeSearch.value),
		division: normalize(elements.divisionFilter.value),
		title: normalize(elements.titleFilter.value),
		location: normalize(elements.locationSearch.value),
	};
}

function applyFilters() {
	const filters = currentFilters();
	state.filtered = state.incidents.filter((incident) => {
		if (filters.global && !buildSearchText(incident).includes(filters.global)) {
			return false;
		}
		if (filters.recordId && !normalize(incident.record_id).includes(filters.recordId)) {
			return false;
		}
		if (filters.date && !normalize(incident.incident_date).includes(filters.date)) {
			return false;
		}
		if (filters.time && !normalize(incident.time).includes(filters.time)) {
			return false;
		}
		if (filters.division && normalize(incident.division) !== filters.division) {
			return false;
		}
		if (filters.title && normalize(incident.title) !== filters.title) {
			return false;
		}
		if (filters.location && !normalize(incident.location).includes(filters.location)) {
			return false;
		}
		return true;
	});
	state.filtered = sortIncidents(state.filtered);
	state.visible = getVisibleIncidents();

	if (!state.visible.some((incident) => incident.record_id === state.selectedId)) {
		state.selectedId = state.visible[0]?.record_id || null;
	}

	renderSummary();
	renderTable();
	renderDetails();
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

function renderSummary() {
	const total = state.incidents.length;
	const filtered = state.filtered.length;

	elements.totalCount.textContent = total;
	elements.filteredCount.textContent = filtered;
	elements.heroTotalCount.textContent = total;
	elements.heroVisibleCount.textContent = filtered;
	elements.topDivision.textContent = topLabel(state.filtered, "division");
	elements.topTitle.textContent = topLabel(state.filtered, "title");
	const visible = state.visible.length;
	elements.resultSummary.textContent = `${visible} of ${filtered} result${filtered === 1 ? "" : "s"} shown`;
	elements.loadingState.textContent = filtered ? `Showing ${visible} of ${filtered} incidents` : "No incidents match your filters";
	renderActiveFilters();
}

function renderActiveFilters() {
	const items = [];
	const filters = [
		["Search", elements.globalSearch.value],
		["Record ID", elements.recordIdSearch.value],
		["Date", elements.dateSearch.value],
		["Time", elements.timeSearch.value],
		["Division", elements.divisionFilter.value],
		["Title", elements.titleFilter.value],
		["Location", elements.locationSearch.value],
	];

	filters.forEach(([label, value]) => {
		if (String(value || "").trim()) {
			items.push(`<button class="filter-tag" type="button" data-filter="${escapeHtml(label)}">${escapeHtml(label)}: ${escapeHtml(value)}</button>`);
		}
	});

	elements.activeFilters.innerHTML = items.join("");
	const buttons = elements.activeFilters.querySelectorAll(".filter-tag");
	buttons.forEach((button) => {
		button.addEventListener("click", () => clearFilter(button.dataset.filter));
	});
}

function clearFilter(label) {
	if (label === "Search") elements.globalSearch.value = "";
	if (label === "Record ID") elements.recordIdSearch.value = "";
	if (label === "Date") elements.dateSearch.value = "";
	if (label === "Time") elements.timeSearch.value = "";
	if (label === "Division") elements.divisionFilter.value = "";
	if (label === "Title") elements.titleFilter.value = "";
	if (label === "Location") elements.locationSearch.value = "";
	applyFilters();
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
			state.selectedId = incident.record_id;
			renderTable();
			renderDetails();
		});

		elements.tableBody.appendChild(row);
	});
}

function renderDetails() {
	const selectedIncident = state.visible.find((incident) => incident.record_id === state.selectedId) || null;

	if (!selectedIncident) {
		elements.detailHint.textContent = "Select an incident row to view more information.";
		elements.detailContent.className = "detail-content empty-state";
		elements.detailContent.textContent = "Pick a record from the table to see its full summary, contact details, and location.";
		return;
	}

	elements.detailHint.textContent = `Record ${selectedIncident.record_id || "N/A"}`;
	elements.detailContent.className = "detail-content fade-in";
	elements.detailContent.innerHTML = `
		<div class="detail-grid">
			<div class="detail-item"><span>Record ID</span><strong>${escapeHtml(selectedIncident.record_id || "N/A")}</strong></div>
			<div class="detail-item"><span>Date</span><strong>${escapeHtml(selectedIncident.incident_date || "N/A")}</strong></div>
			<div class="detail-item"><span>Time</span><strong>${escapeHtml(selectedIncident.time || "N/A")}</strong></div>
			<div class="detail-item"><span>Division</span><strong>${escapeHtml(selectedIncident.division || "N/A")}</strong></div>
			<div class="detail-item"><span>Title</span><strong>${escapeHtml(selectedIncident.title || "N/A")}</strong></div>
			<div class="detail-item"><span>Location</span><strong>${escapeHtml(selectedIncident.location || "N/A")}</strong></div>
			<div class="detail-item"><span>Adults Arrested</span><strong>${escapeHtml(selectedIncident.adults_arrested || "N/A")}</strong></div>
			<div class="detail-item"><span>PD Contact & Number</span><strong>${escapeHtml(selectedIncident.pd_contact_number || "N/A")}</strong></div>
		</div>
		<div class="detail-summary">
			<strong>Summary</strong>
			<p>${escapeHtml(selectedIncident.summary || "No summary provided.")}</p>
		</div>
	`;
}

function resetFilters() {
	elements.globalSearch.value = "";
	elements.recordIdSearch.value = "";
	elements.dateSearch.value = "";
	elements.timeSearch.value = "";
	elements.divisionFilter.value = "";
	elements.titleFilter.value = "";
	elements.locationSearch.value = "";
	elements.pageSizeSelect.value = "10";
	elements.sortSelect.value = "newest";
	state.pageSize = "10";
	state.sortMode = "newest";
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

function wireEvents() {
	[
		elements.globalSearch,
		elements.recordIdSearch,
		elements.dateSearch,
		elements.timeSearch,
		elements.divisionFilter,
		elements.titleFilter,
		elements.locationSearch,
	].forEach((element) => {
		element.addEventListener("input", applyFilters);
		element.addEventListener("change", applyFilters);
	});

	elements.pageSizeSelect.addEventListener("change", () => {
		state.pageSize = elements.pageSizeSelect.value;
		state.visible = getVisibleIncidents();

		if (!state.visible.some((incident) => incident.record_id === state.selectedId)) {
			state.selectedId = state.visible[0]?.record_id || null;
		}

		renderSummary();
		renderTable();
		renderDetails();
	});

	async function runUpdate() {
		elements.updateButton.disabled = true;
		elements.loadingState.textContent = "Updating data... this can take a minute";

		try {
			const response = await fetch("/api/update", { method: "POST" });
			const payload = await response.json();

			if (!response.ok) {
				throw new Error(payload.detail || `Request failed: ${response.status}`);
			}

			await loadIncidents();
			elements.loadingState.textContent = `Update complete: ${payload.current_count} incidents saved (${payload.new_count} new)`;
		} catch (error) {
			elements.loadingState.textContent = `Update failed: ${error.message}`;
		} finally {
			elements.updateButton.disabled = false;
		}
	}

	elements.sortSelect.addEventListener("change", () => {
		state.sortMode = elements.sortSelect.value;
		applyFilters();
	});

	elements.updateButton.addEventListener("click", runUpdate);

	elements.exportButton.addEventListener("click", exportFilteredResults);

	elements.resetButton.addEventListener("click", resetFilters);

	document.addEventListener("keydown", (event) => {
		if (event.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "SELECT") {
			event.preventDefault();
			elements.globalSearch.focus();
		}
	});
}

async function loadIncidents() {
	const response = await fetch("/api/incidents");
	if (!response.ok) {
		throw new Error(`Request failed: ${response.status}`);
	}

	const payload = await response.json();
	state.incidents = sortIncidentsNewestFirst(payload.incidents || []);
	state.filtered = [...state.incidents];
	state.filtered = sortIncidents(state.filtered);
	state.visible = getVisibleIncidents();
	state.selectedId = state.visible[0]?.record_id || null;

	fillSelect(elements.divisionFilter, uniqueValues(state.incidents, "division"), "All divisions");
	fillSelect(elements.titleFilter, uniqueValues(state.incidents, "title"), "All incident types");

	renderSummary();
	renderTable();
	renderDetails();
}

async function startApp() {
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
