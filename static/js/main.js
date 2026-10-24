/**
 * Kavach DPDP Readiness Client-side Application
 */
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

function initApp() {
    initGlobalAlerts();
    initDemoScanButtons();

    if (document.querySelector(".dashboard-page")) {
        initDashboard();
    } else if (document.querySelector(".scanner-page")) {
        initScanner();
    } else if (document.querySelector(".data-map-page")) {
        initDataMap();
    } else if (document.querySelector(".risk-analysis-page")) {
        initRiskAnalysis();
    }
}

/* ==========================================================================
   Global Utilities & Error Handling
   ========================================================================== */

function showGlobalAlert(message, isSuccess = false) {
    const alertEl = document.getElementById("global-alert");
    const textEl = document.getElementById("alert-text");
    if (!alertEl || !textEl) return;

    textEl.textContent = message;
    alertEl.className = "global-alert" + (isSuccess ? " alert-success" : "");
    alertEl.style.display = "flex";

    if (isSuccess) {
        setTimeout(() => {
            alertEl.style.display = "none";
        }, 5000);
    }
}

function dismissAlert() {
    const alertEl = document.getElementById("global-alert");
    if (alertEl) alertEl.style.display = "none";
}

function initGlobalAlerts() {
    const dismissBtn = document.getElementById("alert-dismiss");
    if (dismissBtn) {
        dismissBtn.addEventListener("click", dismissAlert);
    }
}

async function apiFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errJson = await response.json().catch(() => null);
            const errMsg = (errJson && errJson.error) ? errJson.error : `Request failed (${response.status} ${response.statusText})`;
            throw new Error(errMsg);
        }
        return await response.json();
    } catch (err) {
        showGlobalAlert(err.message || "An unexpected error occurred while contacting the server.");
        throw err;
    }
}

function initDemoScanButtons() {
    const demoButtons = document.querySelectorAll(
        "#btn-scan-demo, #btn-scan-demo-scanner, #btn-scan-demo-map, #btn-scan-demo-risk, #btn-empty-scan-demo"
    );

    demoButtons.forEach(btn => {
        btn.addEventListener("click", async () => {
            setBtnLoading(btn, true, "Scanning demo data...");
            try {
                const res = await apiFetch("/api/scan-demo", { method: "POST" });
                showGlobalAlert("Demo dataset scanned successfully! Inventory and readiness score updated.", true);
                reloadCurrentPageData();
            } catch (err) {
                // Handled in apiFetch
            } finally {
                setBtnLoading(btn, false, "Scan demo data");
            }
        });
    });
}

function setBtnLoading(btn, isLoading, text) {
    btn.disabled = isLoading;
    const textSpan = btn.querySelector(".btn-text");
    if (textSpan) {
        textSpan.textContent = text;
    } else {
        btn.textContent = text;
    }
}

function reloadCurrentPageData() {
    if (document.querySelector(".dashboard-page")) {
        loadDashboardData();
    } else if (document.querySelector(".scanner-page")) {
        loadScannerData();
    } else if (document.querySelector(".data-map-page")) {
        loadDataMap();
    } else if (document.querySelector(".risk-analysis-page")) {
        loadRiskAnalysisData();
    }
}

/* ==========================================================================
   Dashboard Page
   ========================================================================== */

function initDashboard() {
    initDropzone();
    initQuestionnaireHandlers();
    loadDashboardData();
}

function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const progressEl = document.getElementById("upload-progress");
    const progressText = document.getElementById("upload-progress-text");

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInput.click();
        }
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
        });
    });

    dropzone.addEventListener("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFileUpload(files);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFileUpload(fileInput.files);
        }
    });

    async function handleFileUpload(files) {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append("files", files[i]);
        }

        if (progressEl) {
            progressEl.style.display = "flex";
            if (progressText) progressText.textContent = `Uploading and scanning ${files.length} file(s)...`;
        }

        try {
            const res = await apiFetch("/api/upload", {
                method: "POST",
                body: formData,
            });
            showGlobalAlert(`Successfully ingested ${res.files_scanned} file(s) and resolved identity clusters.`, true);
            loadDashboardData();
        } catch (err) {
            // Handled
        } finally {
            if (progressEl) progressEl.style.display = "none";
            fileInput.value = "";
        }
    }
}

async function loadDashboardData() {
    try {
        const [inventory, risks] = await Promise.all([
            apiFetch("/api/inventory"),
            apiFetch("/api/risks"),
        ]);

        const emptyState = document.getElementById("empty-state");
        const dashContent = document.getElementById("dashboard-content");

        if (inventory.total_sources === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (dashContent) dashContent.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (dashContent) dashContent.style.display = "block";

        // Update KPIs
        const kpiSources = document.getElementById("kpi-sources");
        const kpiRecords = document.getElementById("kpi-records");
        const kpiPeople = document.getElementById("kpi-people");
        const kpiSensitive = document.getElementById("kpi-sensitive-sources");

        if (kpiSources) kpiSources.textContent = inventory.total_sources;
        if (kpiRecords) kpiRecords.textContent = inventory.total_records.toLocaleString();
        if (kpiPeople) kpiPeople.textContent = inventory.total_people.toLocaleString();

        const sensitiveCount = inventory.sources.filter(s => s.has_sensitive).length;
        if (kpiSensitive) kpiSensitive.textContent = sensitiveCount;

        // Update Readiness Score & Deductions
        updateScoreAndDeductions(risks);

        // Update Top 5 Risks
        updateTopRisks(risks.rules);

        // Update Questionnaire Toggles from facts
        if (risks.facts) {
            syncQuestionnaireToggles(risks.facts);
        }
    } catch (err) {
        console.error("Failed to load dashboard data", err);
    }
}

function updateScoreAndDeductions(risks) {
    const scoreNum = document.getElementById("readiness-score");
    const scoreBadge = document.getElementById("score-status-badge");
    const scoreSummary = document.getElementById("score-summary");
    const deductionsList = document.getElementById("deductions-list");

    const score = risks.readiness_score !== undefined ? risks.readiness_score : 100;

    if (scoreNum) scoreNum.textContent = score;

    if (scoreBadge) {
        if (score >= 80) {
            scoreBadge.className = "badge badge-ok";
            scoreBadge.textContent = "High Readiness";
        } else if (score >= 50) {
            scoreBadge.className = "badge badge-med";
            scoreBadge.textContent = "Moderate Readiness";
        } else {
            scoreBadge.className = "badge badge-critical";
            scoreBadge.textContent = "Action Required";
        }
    }

    if (scoreSummary) {
        const count = (risks.deductions || []).length;
        scoreSummary.textContent = count === 0
            ? "Fully aligned with evaluated DPDP obligations."
            : `${risks.total_deductions} points deducted across ${count} triggered rule(s).`;
    }

    if (deductionsList) {
        deductionsList.innerHTML = "";
        const deductions = risks.deductions || [];
        if (deductions.length === 0) {
            deductionsList.innerHTML = '<li class="deduction-item empty-deduction">No deductions recorded. Full readiness achieved.</li>';
        } else {
            deductions.forEach(d => {
                const li = document.createElement("li");
                li.className = "deduction-item";
                li.innerHTML = `
                    <div class="deduction-info">
                        <div class="deduction-title">
                            <span class="badge badge-${escapeHtml(d.severity)}">${escapeHtml(d.severity)}</span>
                            ${escapeHtml(d.title)}
                        </div>
                        <div class="deduction-reason">${escapeHtml(d.reason)}</div>
                    </div>
                    <div class="deduction-points">-${escapeHtml(String(d.points))} pts</div>
                `;
                deductionsList.appendChild(li);
            });
        }
    }
}

function updateTopRisks(rules) {
    const tbody = document.getElementById("top-risks-tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    const triggered = (rules || []).filter(r => r.status === "triggered");

    const severityOrder = { critical: 4, high: 3, med: 2, low: 1 };
    triggered.sort((a, b) => (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0));

    const top5 = triggered.slice(0, 5);

    if (top5.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">No triggered compliance risks detected! All evaluated rules passed.</td></tr>';
        return;
    }

    top5.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><span class="badge badge-${escapeHtml(r.severity)}">${escapeHtml(r.severity)}</span></td>
            <td><strong>${escapeHtml(r.title)}</strong></td>
            <td><span class="badge badge-citation">${escapeHtml(r.citation_hint)} <span class="tag-verify">verify</span></span></td>
            <td class="text-danger"><strong>-${escapeHtml(String(r.deduction))}</strong></td>
            <td>${escapeHtml(r.remediation)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function syncQuestionnaireToggles(facts) {
    const keys = ["cctv", "personal_phones", "vendors", "breach_contact", "retention_policy", "children_served"];
    keys.forEach(k => {
        const checkbox = document.getElementById(`q-${k.replace(/_/g, "-")}`);
        const stateLabel = document.getElementById(`q-${k.replace(/_/g, "-")}-label`);
        if (checkbox) {
            const isYes = facts[k] === "yes";
            checkbox.checked = isYes;
            if (stateLabel) {
                stateLabel.textContent = isYes ? "Yes" : "No";
            }
        }
    });
}

function initQuestionnaireHandlers() {
    const form = document.getElementById("questionnaire-form");
    if (!form) return;

    const checkboxes = form.querySelectorAll(".toggle-input");
    checkboxes.forEach(cb => {
        cb.addEventListener("change", async () => {
            const key = cb.dataset.key;
            const isChecked = cb.checked;
            const label = document.getElementById(`q-${key.replace(/_/g, "-")}-label`);
            if (label) label.textContent = isChecked ? "Yes" : "No";

            // Gather all current answers
            const answers = {};
            checkboxes.forEach(c => {
                answers[c.dataset.key] = c.checked ? "yes" : "no";
            });

            try {
                // Post to questionnaire, then get updated risks live
                await apiFetch("/api/questionnaire", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ answers }),
                });

                const risks = await apiFetch("/api/risks");
                updateScoreAndDeductions(risks);
                updateTopRisks(risks.rules);
            } catch (err) {
                // Handled
            }
        });
    });
}

/* ==========================================================================
   Scanner Page
   ========================================================================== */

let scannerFindings = [];
let filteredFindings = [];
let scannerCurrentPage = 1;
const FINDINGS_PAGE_SIZE = 50;

function initScanner() {
    const filterSource = document.getElementById("filter-source");
    const filterCategory = document.getElementById("filter-category");
    const filterSearch = document.getElementById("filter-search");
    const btnPrev = document.getElementById("btn-findings-prev");
    const btnNext = document.getElementById("btn-findings-next");

    if (filterSource) filterSource.addEventListener("change", applyFindingsFilters);
    if (filterCategory) filterCategory.addEventListener("change", applyFindingsFilters);
    if (filterSearch) filterSearch.addEventListener("input", applyFindingsFilters);

    if (btnPrev) {
        btnPrev.addEventListener("click", () => {
            if (scannerCurrentPage > 1) {
                scannerCurrentPage--;
                renderFindingsPage();
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener("click", () => {
            const maxPage = Math.ceil(filteredFindings.length / FINDINGS_PAGE_SIZE);
            if (scannerCurrentPage < maxPage) {
                scannerCurrentPage++;
                renderFindingsPage();
            }
        });
    }

    loadScannerData();
}

async function loadScannerData() {
    try {
        const [inventory, findingsData] = await Promise.all([
            apiFetch("/api/inventory"),
            apiFetch("/api/findings"),
        ]);

        const emptyState = document.getElementById("scanner-empty-state");
        const content = document.getElementById("scanner-content");

        if (inventory.total_sources === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (content) content.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (content) content.style.display = "block";

        // Summary stats strip
        const statSources = document.getElementById("scanner-stat-sources");
        const statRecords = document.getElementById("scanner-stat-records");
        const statFindings = document.getElementById("scanner-stat-findings");
        const statSensitive = document.getElementById("scanner-stat-sensitive");

        if (statSources) statSources.textContent = inventory.total_sources;
        if (statRecords) statRecords.textContent = inventory.total_records.toLocaleString();
        if (statFindings) statFindings.textContent = findingsData.total.toLocaleString();

        const sensitiveCount = inventory.sources.filter(s => s.has_sensitive).length;
        if (statSensitive) statSensitive.textContent = sensitiveCount;

        // Render Per-Source Inventory Table
        renderSourcesTable(inventory.sources, findingsData.source_category_counts || {});

        // Store findings & populate dropdown filters
        scannerFindings = findingsData.findings || [];
        populateFindingsFilters(inventory.sources, findingsData.category_counts || {});

        // Initial render
        applyFindingsFilters();
    } catch (err) {
        console.error("Failed to load scanner data", err);
    }
}

function renderSourcesTable(sources, sourceCategoryCounts) {
    const tbody = document.getElementById("sources-tbody");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (!sources || sources.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No sources available.</td></tr>';
        return;
    }

    sources.forEach(s => {
        const tr = document.createElement("tr");

        const countsMap = sourceCategoryCounts[String(s.id)] || {};
        const catBadges = Object.keys(countsMap).map(cat => {
            const isSens = ["aadhaar", "health_term", "bank_account", "pan"].includes(cat);
            return `<span class="badge ${isSens ? 'badge-critical' : 'badge-neutral'}">${escapeHtml(cat)} (${countsMap[cat]})</span>`;
        }).join(" ");

        const sensBadge = s.has_sensitive
            ? '<span class="badge badge-critical">Sensitive PII</span>'
            : '<span class="badge badge-ok">Standard</span>';

        tr.innerHTML = `
            <td><strong>${escapeHtml(s.filename)}</strong></td>
            <td><span class="badge badge-neutral">.${escapeHtml(s.type)}</span></td>
            <td>${escapeHtml(String(s.record_count))}</td>
            <td><div class="category-tags-list">${catBadges || '<span class="text-muted">None</span>'}</div></td>
            <td>${sensBadge}</td>
            <td class="text-muted">${escapeHtml(s.scanned_at || 'Just now')}</td>
        `;
        tbody.appendChild(tr);
    });
}

function populateFindingsFilters(sources, categoryCounts) {
    const filterSource = document.getElementById("filter-source");
    const filterCategory = document.getElementById("filter-category");

    if (filterSource) {
        const curVal = filterSource.value;
        filterSource.innerHTML = '<option value="">All Sources</option>';
        sources.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.filename;
            opt.textContent = `${s.filename} (${s.type})`;
            filterSource.appendChild(opt);
        });
        filterSource.value = curVal;
    }

    if (filterCategory) {
        const curVal = filterCategory.value;
        filterCategory.innerHTML = '<option value="">All Categories</option>';
        Object.keys(categoryCounts).sort().forEach(cat => {
            const opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = `${cat} (${categoryCounts[cat]})`;
            filterCategory.appendChild(opt);
        });
        filterCategory.value = curVal;
    }
}

function applyFindingsFilters() {
    const sourceVal = (document.getElementById("filter-source")?.value || "").toLowerCase();
    const catVal = (document.getElementById("filter-category")?.value || "").toLowerCase();
    const searchVal = (document.getElementById("filter-search")?.value || "").toLowerCase().trim();

    filteredFindings = scannerFindings.filter(f => {
        if (sourceVal && f.source_name.toLowerCase() !== sourceVal) return false;
        if (catVal && f.category.toLowerCase() !== catVal) return false;
        if (searchVal) {
            const matchSample = (f.masked_sample || "").toLowerCase().includes(searchVal);
            const matchKey = (f.record_key || "").toLowerCase().includes(searchVal);
            const matchCat = (f.category || "").toLowerCase().includes(searchVal);
            if (!matchSample && !matchKey && !matchCat) return false;
        }
        return true;
    });

    scannerCurrentPage = 1;
    renderFindingsPage();
}

function renderFindingsPage() {
    const tbody = document.getElementById("findings-tbody");
    const countBadge = document.getElementById("findings-count-badge");
    const pageInfo = document.getElementById("findings-page-info");
    const btnPrev = document.getElementById("btn-findings-prev");
    const btnNext = document.getElementById("btn-findings-next");

    if (!tbody) return;

    const total = filteredFindings.length;
    if (countBadge) countBadge.textContent = `Showing ${total.toLocaleString()} findings`;

    if (total === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No findings match the selected filters.</td></tr>';
        if (pageInfo) pageInfo.textContent = "";
        if (btnPrev) btnPrev.disabled = true;
        if (btnNext) btnNext.disabled = true;
        return;
    }

    const startIdx = (scannerCurrentPage - 1) * FINDINGS_PAGE_SIZE;
    const endIdx = Math.min(startIdx + FINDINGS_PAGE_SIZE, total);
    const pageItems = filteredFindings.slice(startIdx, endIdx);

    tbody.innerHTML = "";
    pageItems.forEach(f => {
        const tr = document.createElement("tr");

        const catBadge = f.is_sensitive
            ? `<span class="badge badge-critical">${escapeHtml(f.category)}</span>`
            : `<span class="badge badge-neutral">${escapeHtml(f.category)}</span>`;

        let details = "-";
        if (f.meta) {
            if (f.meta.is_minor) {
                details = '<span class="badge badge-critical">Minor (&lt;18)</span>';
            } else if (f.meta.condition) {
                details = escapeHtml(f.meta.condition);
            } else if (f.meta.raw_header) {
                details = `Column: ${escapeHtml(f.meta.raw_header)}`;
            }
        }

        const confPct = Math.round((f.confidence || 1.0) * 100);

        tr.innerHTML = `
            <td><strong>${escapeHtml(f.source_name)}</strong></td>
            <td><code class="sample-code">${escapeHtml(f.record_key || f.location)}</code></td>
            <td>${catBadge}</td>
            <td><code class="sample-code">${escapeHtml(f.masked_sample)}</code></td>
            <td>${confPct}%</td>
            <td>${details}</td>
        `;
        tbody.appendChild(tr);
    });

    const maxPage = Math.ceil(total / FINDINGS_PAGE_SIZE);
    if (pageInfo) {
        pageInfo.textContent = `Page ${scannerCurrentPage} of ${maxPage} (${startIdx + 1}–${endIdx} of ${total})`;
    }
    if (btnPrev) btnPrev.disabled = (scannerCurrentPage <= 1);
    if (btnNext) btnNext.disabled = (scannerCurrentPage >= maxPage);
}

/* ==========================================================================
   Data Map Page (Cytoscape.js)
   ========================================================================== */

let cySources = null;
let cyPerson = null;
let dataMapPeople = [];

function initDataMap() {
    const btnModeSources = document.getElementById("mode-btn-sources");
    const btnModePerson = document.getElementById("mode-btn-person");
    const viewSources = document.getElementById("view-mode-sources");
    const viewPerson = document.getElementById("view-mode-person");

    const personSelect = document.getElementById("person-select");
    const personSearch = document.getElementById("person-search-input");

    const btnResetSources = document.getElementById("btn-reset-sources-zoom");
    const btnResetPerson = document.getElementById("btn-reset-person-zoom");

    if (btnModeSources && btnModePerson) {
        btnModeSources.addEventListener("click", () => {
            btnModeSources.classList.add("active");
            btnModeSources.setAttribute("aria-pressed", "true");
            btnModePerson.classList.remove("active");
            btnModePerson.setAttribute("aria-pressed", "false");

            viewSources.style.display = "block";
            viewPerson.style.display = "none";
            if (cySources) {
                cySources.resize();
                cySources.fit();
            }
        });

        btnModePerson.addEventListener("click", () => {
            btnModePerson.classList.add("active");
            btnModePerson.setAttribute("aria-pressed", "true");
            btnModeSources.classList.remove("active");
            btnModeSources.setAttribute("aria-pressed", "false");

            viewPerson.style.display = "block";
            viewSources.style.display = "none";
            if (cyPerson) {
                cyPerson.resize();
                cyPerson.fit();
            }
            if (dataMapPeople.length === 0) {
                loadPeopleList();
            }
        });
    }

    if (btnResetSources) {
        btnResetSources.addEventListener("click", () => {
            if (cySources) cySources.fit();
        });
    }

    if (btnResetPerson) {
        btnResetPerson.addEventListener("click", () => {
            if (cyPerson) cyPerson.fit();
        });
    }

    if (personSelect) {
        personSelect.addEventListener("change", () => {
            const pid = personSelect.value;
            if (pid) loadPersonGraph(pid);
        });
    }

    if (personSearch) {
        personSearch.addEventListener("input", () => {
            filterPersonDropdown(personSearch.value);
        });
    }

    loadDataMap();
}

async function loadDataMap() {
    try {
        const [inventory, findingsData] = await Promise.all([
            apiFetch("/api/inventory"),
            apiFetch("/api/findings"),
        ]);

        const emptyState = document.getElementById("map-empty-state");
        const mapContent = document.getElementById("map-content");

        if (inventory.total_sources === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (mapContent) mapContent.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (mapContent) mapContent.style.display = "block";

        renderSourcesGraph(inventory.sources, findingsData);
        loadPeopleList();
    } catch (err) {
        console.error("Failed to load Data Map data", err);
    }
}

function renderSourcesGraph(sources, findingsData) {
    const container = document.getElementById("cy-sources-categories");
    if (!container || typeof cytoscape === "undefined") return;

    const elements = [];
    const sourceCatCounts = findingsData.source_category_counts || {};
    const catCounts = findingsData.category_counts || {};
    const sensitiveCats = new Set(["aadhaar", "health_term", "bank_account", "pan"]);

    // Add source nodes
    sources.forEach(s => {
        elements.push({
            group: "nodes",
            data: {
                id: `src_${s.id}`,
                label: `${s.filename}\n(${s.type.toUpperCase()})`,
                nodeType: "source",
                recordCount: s.record_count,
            },
        });
    });

    // Add category nodes
    Object.keys(catCounts).forEach(cat => {
        const isSens = sensitiveCats.has(cat);
        const count = catCounts[cat];
        elements.push({
            group: "nodes",
            data: {
                id: `cat_${cat}`,
                label: isSens ? `${cat} [Sensitive]\n(${count})` : `${cat}\n(${count})`,
                nodeType: isSens ? "sensitive_category" : "category",
                count: count,
            },
        });
    });

    // Add edges
    sources.forEach(s => {
        const cats = sourceCatCounts[String(s.id)] || {};
        Object.keys(cats).forEach(cat => {
            const cnt = cats[cat];
            elements.push({
                group: "edges",
                data: {
                    id: `edge_${s.id}_${cat}`,
                    source: `src_${s.id}`,
                    target: `cat_${cat}`,
                    weight: cnt,
                    label: `${cnt}`,
                },
            });
        });
    });

    if (cySources) {
        cySources.destroy();
    }

    cySources = cytoscape({
        container: container,
        elements: elements,
        style: [
            {
                selector: 'node[nodeType = "source"]',
                style: {
                    "shape": "round-rectangle",
                    "background-color": "#1e3a8a",
                    "color": "#ffffff",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "text-wrap": "wrap",
                    "font-size": "12px",
                    "font-weight": "bold",
                    "width": "110px",
                    "height": "60px",
                    "border-width": 2,
                    "border-color": "#3b82f6",
                },
            },
            {
                selector: 'node[nodeType = "category"]',
                style: {
                    "shape": "ellipse",
                    "background-color": "#0284c7",
                    "color": "#ffffff",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "text-wrap": "wrap",
                    "font-size": "11px",
                    "font-weight": "bold",
                    "width": "mapData(count, 1, 100, 50, 95)",
                    "height": "mapData(count, 1, 100, 50, 95)",
                    "border-width": 2,
                    "border-color": "#bae6fd",
                },
            },
            {
                selector: 'node[nodeType = "sensitive_category"]',
                style: {
                    "shape": "ellipse",
                    "background-color": "#dc2626",
                    "color": "#ffffff",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "text-wrap": "wrap",
                    "font-size": "11px",
                    "font-weight": "bold",
                    "width": "mapData(count, 1, 100, 60, 110)",
                    "height": "mapData(count, 1, 100, 60, 110)",
                    "border-width": 3,
                    "border-color": "#fecaca",
                },
            },
            {
                selector: "edge",
                style: {
                    "width": "mapData(weight, 1, 30, 1.5, 5)",
                    "line-color": "#94a3b8",
                    "target-arrow-color": "#94a3b8",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "opacity": 0.85,
                    "label": "data(label)",
                    "font-size": "10px",
                    "color": "#334155",
                    "text-background-opacity": 0.8,
                    "text-background-color": "#ffffff",
                    "text-background-padding": 2,
                },
            },
        ],
        layout: {
            name: "cose",
            idealEdgeLength: 120,
            nodeOverlap: 20,
            refresh: 20,
            fit: true,
            padding: 30,
            randomize: false,
            componentSpacing: 100,
            nodeRepulsion: 400000,
            edgeElasticity: 100,
            nestingFactor: 5,
            gravity: 80,
            numIter: 1000,
            animate: false,
        },
    });
}

async function loadPeopleList() {
    try {
        const data = await apiFetch("/api/people");
        dataMapPeople = data.people || [];
        populatePersonDropdown(dataMapPeople);

        if (dataMapPeople.length > 0) {
            const firstId = dataMapPeople[0].id;
            loadPersonGraph(firstId);
        }
    } catch (err) {
        console.error("Failed to load people list", err);
    }
}

function populatePersonDropdown(people) {
    const select = document.getElementById("person-select");
    if (!select) return;

    select.innerHTML = "";
    if (people.length === 0) {
        select.innerHTML = '<option value="">No resolved principals</option>';
        return;
    }

    people.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.label} – ${p.masked_name} (${p.record_count} records across ${p.source_count} sources)`;
        select.appendChild(opt);
    });
}

function filterPersonDropdown(query) {
    const q = (query || "").toLowerCase().trim();
    const filtered = dataMapPeople.filter(p => {
        return p.label.toLowerCase().includes(q) || (p.masked_name || "").toLowerCase().includes(q);
    });
    populatePersonDropdown(filtered);
    if (filtered.length > 0) {
        loadPersonGraph(filtered[0].id);
    }
}

async function loadPersonGraph(personId) {
    try {
        const personData = await apiFetch(`/api/people/${personId}`);
        renderPersonGraph(personData);
        // Initially show person summary in side panel
        showPersonInSidePanel(personData);
    } catch (err) {
        console.error("Failed to load person detail", err);
    }
}

function renderPersonGraph(person) {
    const container = document.getElementById("cy-person");
    if (!container || typeof cytoscape === "undefined") return;

    const elements = [];

    // Central Person Node
    elements.push({
        group: "nodes",
        data: {
            id: `person_${person.id}`,
            label: `${person.label}\n${person.masked_name}`,
            nodeType: "person",
            personData: person,
        },
    });

    // Record Nodes & Edges
    (person.records || []).forEach((r, idx) => {
        const recId = `rec_${idx}`;
        const isStrong = r.link_type === "strong";

        elements.push({
            group: "nodes",
            data: {
                id: recId,
                label: `${r.source}\n${r.record_key}`,
                nodeType: "record",
                recordData: r,
            },
        });

        elements.push({
            group: "edges",
            data: {
                id: `edge_p_${recId}`,
                source: `person_${person.id}`,
                target: recId,
                isStrong: isStrong,
                label: isStrong ? "strong match" : "probable (name-only)",
            },
        });
    });

    if (cyPerson) {
        cyPerson.destroy();
    }

    cyPerson = cytoscape({
        container: container,
        elements: elements,
        style: [
            {
                selector: 'node[nodeType = "person"]',
                style: {
                    "shape": "ellipse",
                    "background-color": "#1e3a8a",
                    "color": "#ffffff",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "text-wrap": "wrap",
                    "font-size": "13px",
                    "font-weight": "bold",
                    "width": "110px",
                    "height": "110px",
                    "border-width": 3,
                    "border-color": "#60a5fa",
                    "cursor": "pointer",
                },
            },
            {
                selector: 'node[nodeType = "record"]',
                style: {
                    "shape": "round-rectangle",
                    "background-color": "#ffffff",
                    "color": "#0f172a",
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "text-wrap": "wrap",
                    "font-size": "11px",
                    "width": "140px",
                    "height": "65px",
                    "border-width": 2,
                    "border-color": "#94a3b8",
                    "cursor": "pointer",
                },
            },
            {
                selector: "edge[?isStrong]",
                style: {
                    "width": 3,
                    "line-color": "#1e3a8a",
                    "line-style": "solid",
                    "target-arrow-color": "#1e3a8a",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "label": "data(label)",
                    "font-size": "10px",
                    "color": "#1e3a8a",
                    "text-background-opacity": 0.8,
                    "text-background-color": "#ffffff",
                    "text-background-padding": 2,
                },
            },
            {
                selector: "edge[!isStrong]",
                style: {
                    "width": 2,
                    "line-color": "#9333ea",
                    "line-style": "dashed",
                    "line-dash-pattern": [6, 3],
                    "target-arrow-color": "#9333ea",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "label": "data(label)",
                    "font-size": "10px",
                    "color": "#9333ea",
                    "text-background-opacity": 0.8,
                    "text-background-color": "#ffffff",
                    "text-background-padding": 2,
                },
            },
        ],
        layout: {
            name: "concentric",
            concentric: function(node) {
                return node.data("nodeType") === "person" ? 2 : 1;
            },
            levelWidth: function() { return 1; },
            padding: 40,
            fit: true,
        },
    });

    // Node click handler for side panel
    cyPerson.on("tap", "node", (evt) => {
        const node = evt.target;
        const nodeType = node.data("nodeType");
        if (nodeType === "record") {
            showRecordInSidePanel(node.data("recordData"));
        } else if (nodeType === "person") {
            showPersonInSidePanel(node.data("personData"));
        }
    });
}

function showPersonInSidePanel(person) {
    const title = document.getElementById("panel-title");
    const subtitle = document.getElementById("panel-subtitle");
    const body = document.getElementById("panel-body");

    if (title) title.textContent = `${person.label} Identity Summary`;
    if (subtitle) subtitle.textContent = "Data Principal entity profile";

    if (body) {
        body.innerHTML = `
            <div class="panel-section">
                <div class="panel-section-title">Principal Details</div>
                <p><strong>Resolved Label:</strong> ${escapeHtml(person.label)}</p>
                <p><strong>Masked Name:</strong> <code class="sample-code">${escapeHtml(person.masked_name || 'N/A')}</code></p>
                <p><strong>Total Linked Records:</strong> ${person.record_count}</p>
            </div>
            <div class="panel-section">
                <div class="panel-section-title">Linked Data Stores</div>
                <p class="text-muted">Click any outer record node in the graph to inspect exact masked PII samples and linkage confidence.</p>
            </div>
        `;
    }
}

function showRecordInSidePanel(record) {
    const title = document.getElementById("panel-title");
    const subtitle = document.getElementById("panel-subtitle");
    const body = document.getElementById("panel-body");

    if (title) title.textContent = `Record: ${record.record_key}`;
    if (subtitle) subtitle.textContent = `Source: ${record.source} (${record.source_type})`;

    if (body) {
        const isStrong = record.link_type === "strong";
        const linkBadge = isStrong
            ? '<span class="badge badge-ok">Strong Link (Aadhaar / Phone)</span>'
            : '<span class="badge badge-med">Probable Link (Name-only)</span>';

        const findingsHtml = (record.findings || []).map(f => {
            const isSens = ["aadhaar", "health_term", "bank_account", "pan"].includes(f.category);
            return `
                <div class="mb-2 p-2" style="background:#f8fafc; border-radius:4px; border:1px solid #e2e8f0;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span class="badge ${isSens ? 'badge-critical' : 'badge-neutral'}">${escapeHtml(f.category)}</span>
                        <span class="text-muted" style="font-size:0.75rem;">${Math.round(f.confidence * 100)}% conf</span>
                    </div>
                    <div><code class="sample-code">${escapeHtml(f.masked_sample)}</code></div>
                    <div class="text-muted" style="font-size:0.75rem; margin-top:2px;">Location: ${escapeHtml(f.location)}</div>
                </div>
            `;
        }).join("");

        body.innerHTML = `
            <div class="panel-section">
                <div class="panel-section-title">Linkage Resolution</div>
                <div class="mb-2">${linkBadge}</div>
                <p><strong>Confidence:</strong> ${Math.round(record.link_confidence * 100)}%</p>
                <p><strong>Record Key:</strong> <code class="sample-code">${escapeHtml(record.record_key)}</code></p>
            </div>
            <div class="panel-section">
                <div class="panel-section-title">Masked Findings in Record (${(record.findings || []).length})</div>
                <div>${findingsHtml || '<p class="text-muted">No findings recorded</p>'}</div>
            </div>
        `;
    }
}

/* ==========================================================================
   Risk Analysis Page
   ========================================================================== */

function initRiskAnalysis() {
    loadRiskAnalysisData();
}

async function loadRiskAnalysisData() {
    try {
        const [inventory, risks] = await Promise.all([
            apiFetch("/api/inventory"),
            apiFetch("/api/risks"),
        ]);

        const emptyState = document.getElementById("risk-empty-state");
        const content = document.getElementById("risk-content");

        if (inventory.total_sources === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (content) content.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (content) content.style.display = "block";

        // Summary strip
        const scoreDisplay = document.getElementById("risk-score-display");
        const triggeredCount = document.getElementById("risk-triggered-count");
        const passedCount = document.getElementById("risk-passed-count");
        const deductionsTotal = document.getElementById("risk-deductions-total");

        const triggered = (risks.rules || []).filter(r => r.status === "triggered");
        const passed = (risks.rules || []).filter(r => r.status !== "triggered");

        if (scoreDisplay) scoreDisplay.textContent = `${risks.readiness_score || 0}/100`;
        if (triggeredCount) triggeredCount.textContent = triggered.length;
        if (passedCount) passedCount.textContent = passed.length;
        if (deductionsTotal) deductionsTotal.textContent = `-${risks.total_deductions || 0}`;

        // Render Triggered Risks
        renderTriggeredRisks(triggered);

        // Render Looks Fine / Passed
        renderPassedRisks(passed);
    } catch (err) {
        console.error("Failed to load risk analysis data", err);
    }
}

function renderTriggeredRisks(triggered) {
    const container = document.getElementById("triggered-risks-container");
    if (!container) return;

    container.innerHTML = "";
    if (triggered.length === 0) {
        container.innerHTML = '<div class="card p-4 text-center text-success"><strong>No compliance risks triggered!</strong> All 12 evaluation criteria are satisfied.</div>';
        return;
    }

    const severityOrder = { critical: 4, high: 3, med: 2, low: 1 };
    triggered.sort((a, b) => (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0));

    triggered.forEach(r => {
        const card = document.createElement("div");
        card.className = `risk-rule-card risk-card-${escapeHtml(r.severity)}`;
        card.innerHTML = `
            <div class="risk-header-row">
                <div class="risk-title-group">
                    <span class="badge badge-${escapeHtml(r.severity)}">${escapeHtml(r.severity)}</span>
                    <h3 class="risk-title">${escapeHtml(r.title)}</h3>
                    <span class="badge badge-citation">${escapeHtml(r.citation_hint)} <span class="tag-verify">verify</span></span>
                </div>
                <div class="risk-points-tag">-${escapeHtml(String(r.deduction))} pts deduction</div>
            </div>
            <div class="risk-remediation">
                <strong>Plain-Language Remediation:</strong> ${escapeHtml(r.remediation)}
            </div>
        `;
        container.appendChild(card);
    });
}

function renderPassedRisks(passed) {
    const container = document.getElementById("passed-risks-container");
    if (!container) return;

    container.innerHTML = "";
    if (passed.length === 0) {
        container.innerHTML = '<div class="card p-4 text-center text-muted">No rules currently passed.</div>';
        return;
    }

    passed.forEach(r => {
        const isEmployeeRule = (r.id === "employee_data_lawful_basis");
        const card = document.createElement("div");
        card.className = "risk-rule-card risk-card-ok";

        const statusBadge = isEmployeeRule
            ? '<span class="badge badge-ok">&#x2714; Lawful Basis (s.7(i))</span>'
            : '<span class="badge badge-ok">&#x2714; Passed / Satisfied</span>';

        card.innerHTML = `
            <div class="risk-header-row">
                <div class="risk-title-group">
                    ${statusBadge}
                    <h3 class="risk-title">${escapeHtml(r.title)}</h3>
                    <span class="badge badge-citation">${escapeHtml(r.citation_hint)} <span class="tag-verify">verify</span></span>
                </div>
                <span class="text-success" style="font-weight:600; font-size:0.85rem;">0 pt deduction</span>
            </div>
            <div class="risk-note">
                <strong>Compliance Status:</strong> ${escapeHtml(r.note || r.remediation)}
            </div>
        `;
        container.appendChild(card);
    });
}

function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
