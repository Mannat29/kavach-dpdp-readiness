/**
 * Kavach DPDP Readiness – Breach Simulator Page Logic
 */

(function () {
    "use strict";

    // Application state
    let inventoryData = null;
    let scenariosData = [];
    let currentSimulation = null;
    let clockInterval = null;
    let cyInstance = null;
    let activeDraftTab = "board_intimation";
    let activeDraftsMap = {};

    document.addEventListener("DOMContentLoaded", () => {
        initBreachSimulator();
    });

    async function initBreachSimulator() {
        initAwarenessInputDefault();
        initErrorAlertDismiss();
        initEmptyStateScanButton();

        try {
            await checkInventoryAndLoad();
        } catch (err) {
            showSimError("Failed to initialize Breach Simulator: " + (err.message || err));
        }
    }

    /** Set default aware_at input to current local time */
    function initAwarenessInputDefault() {
        const input = document.getElementById("input-aware-at");
        if (!input) return;
        const now = new Date();
        // Pad single digits
        const pad = (n) => (n < 10 ? "0" + n : n);
        const yyyy = now.getFullYear();
        const mm = pad(now.getMonth() + 1);
        const dd = pad(now.getDate());
        const hh = pad(now.getHours());
        const min = pad(now.getMinutes());
        input.value = `${yyyy}-${mm}-${dd}T${hh}:${min}`;
    }

    function initErrorAlertDismiss() {
        const btn = document.getElementById("btn-dismiss-sim-error");
        if (btn) {
            btn.addEventListener("click", () => {
                hideSimError();
            });
        }
    }

    function showSimError(msg) {
        const alertEl = document.getElementById("sim-error-alert");
        const textEl = document.getElementById("sim-error-text");
        if (alertEl && textEl) {
            textEl.textContent = msg;
            alertEl.style.display = "flex";
            alertEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }

    function hideSimError() {
        const alertEl = document.getElementById("sim-error-alert");
        if (alertEl) {
            alertEl.style.display = "none";
        }
    }

    function initEmptyStateScanButton() {
        const btn = document.getElementById("btn-sim-empty-scan");
        if (btn) {
            btn.addEventListener("click", async () => {
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span class="btn-icon" aria-hidden="true">&#x231B;</span> Scanning demo data...';
                try {
                    const res = await fetch("/api/scan-demo", { method: "POST" });
                    if (!res.ok) {
                        const errData = await res.json().catch(() => ({}));
                        throw new Error(errData.error || "Failed to scan demo dataset.");
                    }
                    await checkInventoryAndLoad();
                } catch (err) {
                    showSimError(err.message || "Failed to scan demo data.");
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }
            });
        }
    }

    /** Check if data sources are ingested */
    async function checkInventoryAndLoad() {
        const emptyState = document.getElementById("sim-empty-state");
        const mainContainer = document.getElementById("sim-main-container");

        const invRes = await fetch("/api/inventory");
        if (!invRes.ok) {
            throw new Error(`Inventory endpoint error: ${invRes.status}`);
        }
        inventoryData = await invRes.json();

        if (!inventoryData.sources || inventoryData.sources.length === 0) {
            if (emptyState) emptyState.style.display = "block";
            if (mainContainer) mainContainer.style.display = "none";
            return;
        }

        if (emptyState) emptyState.style.display = "none";
        if (mainContainer) mainContainer.style.display = "block";

        populateCustomSources(inventoryData.sources);
        await loadScenarios();
        initFormHandler();
        initDraftTabs();
    }

    /** Populate checkboxes for custom scenario sources */
    function populateCustomSources(sources) {
        const container = document.getElementById("custom-sources-list");
        if (!container) return;
        container.innerHTML = "";

        sources.forEach((s, idx) => {
            const label = document.createElement("label");
            label.className = "custom-source-item";
            label.setAttribute("for", `custom-src-${idx}`);

            const chk = document.createElement("input");
            chk.type = "checkbox";
            chk.className = "custom-source-checkbox";
            chk.id = `custom-src-${idx}`;
            chk.value = s.filename;
            chk.checked = true; // Default selected

            const txt = document.createElement("span");
            txt.textContent = `${s.filename} (${s.record_count} records)`;

            label.appendChild(chk);
            label.appendChild(txt);
            container.appendChild(label);
        });
    }

    /** Load scenario definitions from API */
    async function loadScenarios() {
        const container = document.getElementById("scenario-cards-container");
        if (!container) return;

        try {
            const res = await fetch("/api/breach/scenarios");
            if (res.ok) {
                const data = await res.json();
                scenariosData = data.scenarios || [];
            }
        } catch (e) {
            console.warn("Could not fetch /api/breach/scenarios, using fallbacks", e);
        }

        if (!scenariosData || scenariosData.length === 0) {
            scenariosData = [
                {
                    id: "owner_phone_stolen",
                    title: "Owner phone stolen",
                    description: "Business owner's mobile device containing WhatsApp client chats, customer records, and informal messages was stolen.",
                    affected_sources: ["whatsapp_chat.txt"]
                },
                {
                    id: "billing_laptop_ransomware",
                    title: "Billing laptop ransomware",
                    description: "Ransomware infection encrypted the billing department laptop, compromising patient billing records and patient details availability and confidentiality.",
                    affected_sources: ["billing.csv", "patients.xlsx"]
                },
                {
                    id: "public_form_link_leaked",
                    title: "Public form link leaked",
                    description: "A public Google Forms / web appointments sheet was exposed with view or edit permissions open to the internet without authentication.",
                    affected_sources: ["appointments_form.csv"]
                },
                {
                    id: "staff_laptop_lost",
                    title: "Staff laptop lost",
                    description: "A staff member lost a work laptop during transit, containing employee records, PAN cards, and payroll bank details.",
                    affected_sources: ["staff.csv"]
                },
                {
                    id: "custom",
                    title: "Custom scenario",
                    description: "Custom breach blast-radius simulation with user-selected source files.",
                    affected_sources: []
                }
            ];
        }

        renderScenarioCards(scenariosData);
    }

    /** Render radio card group for breach scenarios */
    function renderScenarioCards(scenarios) {
        const container = document.getElementById("scenario-cards-container");
        if (!container) return;
        container.innerHTML = "";

        scenarios.forEach((sc, idx) => {
            const label = document.createElement("label");
            label.className = `scenario-card-label ${idx === 0 ? "selected" : ""}`;
            label.setAttribute("for", `scenario-opt-${sc.id}`);

            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "scenario";
            radio.id = `scenario-opt-${sc.id}`;
            radio.value = sc.id;
            radio.className = "scenario-radio-input";
            if (idx === 0) radio.checked = true;

            const title = document.createElement("span");
            title.className = "scenario-card-title";
            title.textContent = sc.title;

            const desc = document.createElement("span");
            desc.className = "scenario-card-desc";
            desc.textContent = sc.description;

            const sourcesWrap = document.createElement("div");
            sourcesWrap.className = "scenario-card-sources";
            if (sc.affected_sources && sc.affected_sources.length > 0) {
                sc.affected_sources.forEach(src => {
                    const tag = document.createElement("span");
                    tag.className = "scenario-source-tag";
                    tag.textContent = src;
                    sourcesWrap.appendChild(tag);
                });
            } else if (sc.id === "custom") {
                const tag = document.createElement("span");
                tag.className = "scenario-source-tag";
                tag.textContent = "Select sources below";
                sourcesWrap.appendChild(tag);
            }

            label.appendChild(radio);
            label.appendChild(title);
            label.appendChild(desc);
            label.appendChild(sourcesWrap);

            // Handle radio changes
            radio.addEventListener("change", () => {
                document.querySelectorAll(".scenario-card-label").forEach(l => l.classList.remove("selected"));
                label.classList.add("selected");

                const customBox = document.getElementById("custom-sources-box");
                if (customBox) {
                    customBox.style.display = sc.id === "custom" ? "block" : "none";
                }
            });

            container.appendChild(label);
        });
    }

    /** Initialize form submit listener */
    function initFormHandler() {
        const form = document.getElementById("breach-form");
        const btnRun = document.getElementById("btn-run-simulation");
        if (!form || !btnRun) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            hideSimError();

            const selectedRadio = document.querySelector('input[name="scenario"]:checked');
            if (!selectedRadio) {
                showSimError("Please select a breach scenario.");
                return;
            }

            const scenarioId = selectedRadio.value;
            const awareInput = document.getElementById("input-aware-at");
            const deviceSelect = document.getElementById("select-device-protected");

            let awareAtIso = null;
            if (awareInput && awareInput.value) {
                try {
                    awareAtIso = new Date(awareInput.value).toISOString();
                } catch (e) {
                    awareAtIso = new Date().toISOString();
                }
            } else {
                awareAtIso = new Date().toISOString();
            }

            const deviceProtected = deviceSelect ? deviceSelect.value : "unknown";

            let customSources = undefined;
            if (scenarioId === "custom") {
                const checkedBoxes = document.querySelectorAll(".custom-source-checkbox:checked");
                customSources = Array.from(checkedBoxes).map(cb => cb.value);
                if (customSources.length === 0) {
                    showSimError("Please select at least one source file for the custom scenario.");
                    return;
                }
            }

            // Disable buttons and show in-flight status
            btnRun.disabled = true;
            const originalBtnHtml = btnRun.innerHTML;
            btnRun.innerHTML = '<span class="btn-icon" aria-hidden="true">&#x231B;</span> <span class="btn-text">Running simulation...</span>';

            try {
                const payload = {
                    scenario: scenarioId,
                    aware_at: awareAtIso,
                    device_protected: deviceProtected,
                };
                if (customSources) {
                    payload.sources = customSources;
                }

                const res = await fetch("/api/breach/simulate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.error || `Simulation failed (${res.status})`);
                }

                const result = await res.json();
                currentSimulation = result;
                displaySimulationResults(result);
            } catch (err) {
                showSimError(err.message || "An unexpected error occurred while running the simulation.");
            } finally {
                btnRun.disabled = false;
                btnRun.innerHTML = originalBtnHtml;
            }
        });
    }

    /** Display all results upon successful simulation */
    function displaySimulationResults(result) {
        const resultsContainer = document.getElementById("simulation-results");
        if (resultsContainer) {
            resultsContainer.style.display = "block";
            resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        // 1. Download all link
        const btnDownloadAll = document.getElementById("btn-download-all");
        if (btnDownloadAll && result.id) {
            btnDownloadAll.href = `/api/breach/${result.id}/export`;
        }

        // 2. Impact Summary
        renderImpactSummary(result);

        // 3. Clocks
        startClocks(result.aware_at);

        // 4. Cytoscape Graph
        renderBlastRadiusGraph(result);

        // 5. Checklist
        renderChecklist(result.first_hour_checklist || []);

        // 6. Drafts
        renderDrafts(result.drafts || {});

        // 7. Recipients
        loadRecipients(result.id);
    }

    /** Escape HTML helper */
    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    /** 2. Impact Summary rendering */
    function renderImpactSummary(result) {
        const severityBadgeContainer = document.getElementById("severity-badge-container");
        const statPeople = document.getElementById("stat-people-affected");
        const statPeopleSub = document.getElementById("stat-people-subtext");
        const statRecords = document.getElementById("stat-records-affected");
        const factorsList = document.getElementById("severity-factors-list");
        const categoriesTableBody = document.getElementById("categories-table-body");

        // Severity badge
        const sev = (result.severity || "medium").toLowerCase();
        const score = result.severity_score !== undefined ? result.severity_score : 0;
        if (severityBadgeContainer) {
            severityBadgeContainer.innerHTML = `
                <span class="badge-severity badge-${sev}">
                    ${sev.toUpperCase()} (${score} PTS)
                </span>
            `;
        }

        // Big Numbers
        const counts = result.counts || {};
        const confCount = counts.confirmed_count !== undefined ? counts.confirmed_count : 0;
        const possCount = counts.possible_count !== undefined ? counts.possible_count : 0;
        const totalPeople = counts.people_count !== undefined ? counts.people_count : (confCount + possCount);
        const peopleRange = counts.range || `${confCount}-${totalPeople}`;
        const totalRecords = counts.records_count !== undefined ? counts.records_count : 0;

        if (statPeople) {
            statPeople.textContent = `${confCount} confirmed + ${possCount} possible`;
        }
        if (statPeopleSub) {
            statPeopleSub.textContent = `Total distinct principals: ${totalPeople} (range: ${peopleRange})`;
        }
        if (statRecords) {
            statRecords.textContent = totalRecords.toLocaleString();
        }

        // Severity Factors
        if (factorsList) {
            factorsList.innerHTML = "";
            const factors = result.severity_factors || [];
            if (factors.length === 0) {
                factorsList.innerHTML = '<li class="text-muted">No severity risk factors triggered.</li>';
            } else {
                factors.forEach(f => {
                    const li = document.createElement("li");
                    const pts = f.points || 0;
                    const ptsClass = pts >= 0 ? "factor-pts-pos" : "factor-pts-neg";
                    const ptsSign = pts > 0 ? "+" : "";
                    li.innerHTML = `
                        <span class="factor-pts ${ptsClass}">${ptsSign}${pts} pts</span>
                        <span class="factor-reason">${escapeHtml(f.reason)}</span>
                    `;
                    factorsList.appendChild(li);
                });
            }
        }

        // Categories Table
        if (categoriesTableBody) {
            categoriesTableBody.innerHTML = "";
            const cats = counts.categories || {};
            const catKeys = Object.keys(cats);
            if (catKeys.length === 0) {
                categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No personal data categories detected.</td></tr>';
            } else {
                catKeys.forEach(k => {
                    const c = cats[k];
                    const tr = document.createElement("tr");
                    const label = (c.category || k).replace(/_/g, " ").toUpperCase();
                    const isHi = Boolean(c.is_high_impact);
                    const hiBadge = isHi
                        ? '<span class="badge badge-critical" aria-label="High impact category">&#x26A0; Yes (High-impact)</span>'
                        : '<span class="badge badge-neutral">Standard</span>';

                    tr.innerHTML = `
                        <td><strong>${escapeHtml(label)}</strong></td>
                        <td>${c.people !== undefined ? c.people : "-"}</td>
                        <td>${c.records !== undefined ? c.records : "-"}</td>
                        <td>${hiBadge}</td>
                    `;
                    categoriesTableBody.appendChild(tr);
                });
            }
        }
    }

    /** 4. Clocks with 1-second live ticker */
    function startClocks(awareAtIso) {
        if (clockInterval) {
            clearInterval(clockInterval);
            clockInterval = null;
        }

        const stage1Timer = document.getElementById("clock-stage1-timer");
        const stage1Status = document.getElementById("clock-stage1-status");
        const stage2Timer = document.getElementById("clock-stage2-timer");
        const stage2Status = document.getElementById("clock-stage2-status");
        const stage2Card = document.getElementById("clock-card-stage2");

        const awareDate = new Date(awareAtIso);
        const deadlineDate = new Date(awareDate.getTime() + 72 * 3600 * 1000);

        function updateTick() {
            const now = new Date();

            // Stage 1: Elapsed time since awareness
            const elapsedMs = Math.max(0, now.getTime() - awareDate.getTime());
            const elapsedSec = Math.floor(elapsedMs / 1000);
            const eDays = Math.floor(elapsedSec / 86400);
            const eHours = Math.floor((elapsedSec % 86400) / 3600);
            const eMins = Math.floor((elapsedSec % 3600) / 60);
            const eSecs = elapsedSec % 60;

            const pad = (n) => (n < 10 ? "0" + n : n);
            let elapsedStr = `${pad(eHours)}h ${pad(eMins)}m ${pad(eSecs)}s elapsed`;
            if (eDays > 0) {
                elapsedStr = `${eDays}d ${elapsedStr}`;
            }

            if (stage1Timer) stage1Timer.textContent = elapsedStr;
            if (stage1Status) stage1Status.textContent = "Requirement: Inform the Board without delay (Section 8(6))";

            // Stage 2: 72 hours deadline countdown
            const remainingMs = deadlineDate.getTime() - now.getTime();
            const remainingSec = Math.floor(remainingMs / 1000);

            if (stage2Card) {
                stage2Card.classList.remove("clock-card-normal", "clock-card-urgent", "clock-card-critical");
            }

            if (remainingSec <= 0) {
                // Expired
                const overdueSec = Math.abs(remainingSec);
                const oHours = Math.floor(overdueSec / 3600);
                const oMins = Math.floor((overdueSec % 3600) / 60);
                if (stage2Timer) stage2Timer.textContent = `00h 00m 00s`;
                if (stage2Status) {
                    stage2Status.innerHTML = `<span class="badge badge-critical">DEADLINE EXPIRED: ${oHours}h ${oMins}m overdue</span>`;
                }
                if (stage2Card) stage2Card.classList.add("clock-card-critical");
            } else if (remainingSec < 6 * 3600) {
                // Critical under 6 hours
                const rHours = Math.floor(remainingSec / 3600);
                const rMins = Math.floor((remainingSec % 3600) / 60);
                const rSecs = remainingSec % 60;
                if (stage2Timer) stage2Timer.textContent = `${pad(rHours)}h ${pad(rMins)}m ${pad(rSecs)}s remaining`;
                if (stage2Status) {
                    stage2Status.innerHTML = `<span class="badge badge-critical">CRITICAL: Under 6 hours remaining</span>`;
                }
                if (stage2Card) stage2Card.classList.add("clock-card-critical");
            } else if (remainingSec < 24 * 3600) {
                // Urgent under 24 hours
                const rHours = Math.floor(remainingSec / 3600);
                const rMins = Math.floor((remainingSec % 3600) / 60);
                const rSecs = remainingSec % 60;
                if (stage2Timer) stage2Timer.textContent = `${pad(rHours)}h ${pad(rMins)}m ${pad(rSecs)}s remaining`;
                if (stage2Status) {
                    stage2Status.innerHTML = `<span class="badge badge-warning">URGENT: Under 24 hours remaining</span>`;
                }
                if (stage2Card) stage2Card.classList.add("clock-card-urgent");
            } else {
                // Normal (> 24 hours)
                const rDays = Math.floor(remainingSec / 86400);
                const rHours = Math.floor((remainingSec % 86400) / 3600);
                const rMins = Math.floor((remainingSec % 3600) / 60);
                const rSecs = remainingSec % 60;
                let remStr = `${pad(rHours)}h ${pad(rMins)}m ${pad(rSecs)}s remaining`;
                if (rDays > 0) {
                    remStr = `${rDays}d ${remStr}`;
                }
                if (stage2Timer) stage2Timer.textContent = remStr;
                if (stage2Status) {
                    stage2Status.innerHTML = `<span class="badge badge-neutral">ON SCHEDULE: Over 24 hours remaining</span>`;
                }
                if (stage2Card) stage2Card.classList.add("clock-card-normal");
            }
        }

        updateTick();
        clockInterval = setInterval(updateTick, 1000);
    }

    /** 3. Blast-Radius Cytoscape Graph rendering */
    function renderBlastRadiusGraph(result) {
        const container = document.getElementById("cy-breach");
        if (!container) return;

        if (typeof cytoscape === "undefined") {
            container.innerHTML = '<div class="p-4 text-center text-muted">Cytoscape visualization library not loaded.</div>';
            return;
        }

        if (cyInstance) {
            cyInstance.destroy();
            cyInstance = null;
        }

        const elements = [];
        const affectedSet = new Set(result.affected_sources || []);
        const allSources = (inventoryData && inventoryData.sources) ? inventoryData.sources : [];

        // If no sources list is in inventoryData, build minimal list from affected sources
        const sourceList = allSources.length > 0 ? allSources : Array.from(affectedSet).map((fn, idx) => ({ id: idx + 1, filename: fn, categories_present: [] }));

        // 1. Source Nodes
        sourceList.forEach(s => {
            const isAff = affectedSet.has(s.filename);
            const fname = s.filename.length > 18 ? s.filename.slice(0, 16) + "…" : s.filename;
            elements.push({
                group: "nodes",
                data: {
                    id: `src_${s.id}`,
                    label: isAff ? `${fname}\n[AFFECTED]` : `${fname}\n(unaffected)`,
                    nodeType: isAff ? "source_affected" : "source_unaffected",
                }
            });
        });

        // 2. Category Nodes
        const categories = (result.counts && result.counts.categories) ? result.counts.categories : {};
        const catKeys = Object.keys(categories);

        catKeys.forEach(cat => {
            const cData = categories[cat];
            const pCount = cData.people || 0;
            const rCount = cData.records || 0;
            const isHi = Boolean(cData.is_high_impact);
            const label = `${cat.replace(/_/g, " ").toUpperCase()}\n${pCount} people (${rCount} recs)`;

            elements.push({
                group: "nodes",
                data: {
                    id: `cat_${cat}`,
                    label: label,
                    nodeType: isHi ? "category_high" : "category_std",
                    peopleCount: pCount,
                }
            });
        });

        // 3. Principal Nodes: Confirmed People and Possible People
        const confCount = (result.counts && result.counts.confirmed_count) || 0;
        const possCount = (result.counts && result.counts.possible_count) || 0;

        elements.push({
            group: "nodes",
            data: {
                id: "node_confirmed_people",
                label: `Confirmed People\n(${confCount})`,
                nodeType: "people_confirmed",
            }
        });

        elements.push({
            group: "nodes",
            data: {
                id: "node_possible_people",
                label: `Possible People\n(${possCount})`,
                nodeType: "people_possible",
            }
        });

        // 4. Edges: Affected Sources -> Categories
        sourceList.forEach(s => {
            if (affectedSet.has(s.filename)) {
                // Link to categories present in this source, or all affected categories if list is empty
                const catsForSource = (s.categories_present && s.categories_present.length > 0)
                    ? s.categories_present.filter(c => catKeys.includes(c))
                    : catKeys;

                catsForSource.forEach(cat => {
                    elements.push({
                        group: "edges",
                        data: {
                            id: `edge_${s.id}_${cat}`,
                            source: `src_${s.id}`,
                            target: `cat_${cat}`,
                            edgeType: "source_to_cat",
                        }
                    });
                });
            }
        });

        // 5. Edges: Categories -> Confirmed / Possible People
        catKeys.forEach(cat => {
            if (confCount > 0) {
                elements.push({
                    group: "edges",
                    data: {
                        id: `edge_${cat}_confirmed`,
                        source: `cat_${cat}`,
                        target: "node_confirmed_people",
                        edgeType: "cat_to_confirmed",
                    }
                });
            }
            if (possCount > 0) {
                elements.push({
                    group: "edges",
                    data: {
                        id: `edge_${cat}_possible`,
                        source: `cat_${cat}`,
                        target: "node_possible_people",
                        edgeType: "cat_to_possible",
                    }
                });
            }
        });

        // Initialize Cytoscape
        cyInstance = cytoscape({
            container: container,
            elements: elements,
            style: [
                {
                    selector: 'node[nodeType = "source_affected"]',
                    style: {
                        "shape": "round-rectangle",
                        "background-color": "#b91c1c",
                        "color": "#ffffff",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "130px",
                        "font-size": "12px",
                        "font-weight": "bold",
                        "width": "140px",
                        "height": "65px",
                        "border-width": 3,
                        "border-color": "#ef4444",
                    }
                },
                {
                    selector: 'node[nodeType = "source_unaffected"]',
                    style: {
                        "shape": "round-rectangle",
                        "background-color": "#94a3b8",
                        "color": "#1e293b",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "130px",
                        "font-size": "12px",
                        "font-weight": "normal",
                        "width": "130px",
                        "height": "55px",
                        "border-width": 1,
                        "border-color": "#cbd5e1",
                        "opacity": 0.65,
                    }
                },
                {
                    selector: 'node[nodeType = "category_std"]',
                    style: {
                        "shape": "ellipse",
                        "background-color": "#0284c7",
                        "color": "#ffffff",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "120px",
                        "font-size": "12px",
                        "font-weight": "bold",
                        "width": "mapData(peopleCount, 0, 30, 80, 130)",
                        "height": "mapData(peopleCount, 0, 30, 80, 130)",
                        "border-width": 2,
                        "border-color": "#38bdf8",
                    }
                },
                {
                    selector: 'node[nodeType = "category_high"]',
                    style: {
                        "shape": "ellipse",
                        "background-color": "#ea580c",
                        "color": "#ffffff",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "120px",
                        "font-size": "12px",
                        "font-weight": "bold",
                        "width": "mapData(peopleCount, 0, 30, 85, 135)",
                        "height": "mapData(peopleCount, 0, 30, 85, 135)",
                        "border-width": 3,
                        "border-color": "#f97316",
                    }
                },
                {
                    selector: 'node[nodeType = "people_confirmed"]',
                    style: {
                        "shape": "round-rectangle",
                        "background-color": "#059669",
                        "color": "#ffffff",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "130px",
                        "font-size": "12px",
                        "font-weight": "bold",
                        "width": "140px",
                        "height": "65px",
                        "border-width": 3,
                        "border-color": "#10b981",
                    }
                },
                {
                    selector: 'node[nodeType = "people_possible"]',
                    style: {
                        "shape": "round-rectangle",
                        "background-color": "#7c3aed",
                        "color": "#ffffff",
                        "label": "data(label)",
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-wrap": "wrap",
                        "text-max-width": "130px",
                        "font-size": "12px",
                        "font-weight": "bold",
                        "width": "140px",
                        "height": "65px",
                        "border-width": 3,
                        "border-style": "dashed",
                        "border-color": "#a855f7",
                    }
                },
                {
                    selector: 'edge[edgeType = "source_to_cat"]',
                    style: {
                        "width": 2.5,
                        "line-color": "#ef4444",
                        "target-arrow-color": "#ef4444",
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                    }
                },
                {
                    selector: 'edge[edgeType = "cat_to_confirmed"]',
                    style: {
                        "width": 2.5,
                        "line-color": "#10b981",
                        "target-arrow-color": "#10b981",
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                    }
                },
                {
                    selector: 'edge[edgeType = "cat_to_possible"]',
                    style: {
                        "width": 2,
                        "line-color": "#a855f7",
                        "line-style": "dashed",
                        "target-arrow-color": "#a855f7",
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                    }
                }
            ],
            layout: {
                name: "breadthfirst",
                directed: true,
                padding: 30,
                spacingFactor: 1.4,
                avoidOverlap: true,
            }
        });

        // Fit button listener
        const btnFit = document.getElementById("btn-fit-graph");
        if (btnFit) {
            btnFit.onclick = () => {
                if (cyInstance) {
                    cyInstance.resize();
                    cyInstance.fit(30);
                }
            };
        }
    }

    /** 6. First-Hour Checklist */
    function renderChecklist(checklistItems) {
        const listEl = document.getElementById("checklist-items");
        const progressEl = document.getElementById("checklist-progress");
        if (!listEl) return;
        listEl.innerHTML = "";

        if (!checklistItems || checklistItems.length === 0) {
            listEl.innerHTML = '<li class="text-muted p-2">No checklist items defined for this scenario.</li>';
            if (progressEl) progressEl.textContent = "0 of 0 completed";
            return;
        }

        const total = checklistItems.length;
        let completed = 0;

        function updateProgress() {
            if (progressEl) {
                progressEl.textContent = `${completed} of ${total} completed`;
            }
        }

        checklistItems.forEach((step, idx) => {
            const li = document.createElement("li");
            li.className = "checklist-item";

            const label = document.createElement("label");
            label.className = "checklist-label";
            label.setAttribute("for", `chk-step-${idx}`);

            const chk = document.createElement("input");
            chk.type = "checkbox";
            chk.className = "checklist-checkbox";
            chk.id = `chk-step-${idx}`;

            const txt = document.createElement("span");
            txt.className = "checklist-text";
            txt.textContent = step;

            chk.addEventListener("change", () => {
                if (chk.checked) {
                    li.classList.add("checked");
                    completed++;
                } else {
                    li.classList.remove("checked");
                    completed--;
                }
                updateProgress();
            });

            label.appendChild(chk);
            label.appendChild(txt);
            li.appendChild(label);
            listEl.appendChild(li);
        });

        updateProgress();
    }

    /** 5. Drafts & Placeholders tabs */
    function initDraftTabs() {
        const tabBtns = document.querySelectorAll(".tab-btn");
        tabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                tabBtns.forEach(b => {
                    b.classList.remove("active");
                    b.setAttribute("aria-selected", "false");
                });
                btn.classList.add("active");
                btn.setAttribute("aria-selected", "true");

                activeDraftTab = btn.dataset.tab;
                displayCurrentDraftTab();
            });
        });

        const btnCopy = document.getElementById("btn-copy-draft");
        if (btnCopy) {
            btnCopy.addEventListener("click", () => {
                const rawText = activeDraftsMap[activeDraftTab] || "";
                if (!rawText) return;

                navigator.clipboard.writeText(rawText).then(() => {
                    const originalHtml = btnCopy.innerHTML;
                    btnCopy.innerHTML = "&#x2714; Copied to clipboard!";
                    btnCopy.classList.add("btn-success");
                    setTimeout(() => {
                        btnCopy.innerHTML = originalHtml;
                        btnCopy.classList.remove("btn-success");
                    }, 2500);
                }).catch(() => {
                    // Fallback
                    const textarea = document.createElement("textarea");
                    textarea.value = rawText;
                    document.body.appendChild(textarea);
                    textarea.select();
                    document.execCommand("copy");
                    document.body.removeChild(textarea);
                    btnCopy.innerHTML = "&#x2714; Copied!";
                    setTimeout(() => {
                        btnCopy.innerHTML = "&#x1F4CB; Copy draft text";
                    }, 2500);
                });
            });
        }
    }

    function renderDrafts(drafts) {
        activeDraftsMap = drafts || {};
        displayCurrentDraftTab();
    }

    function displayCurrentDraftTab() {
        const viewer = document.getElementById("draft-text-container");
        if (!viewer) return;

        const rawText = activeDraftsMap[activeDraftTab] || "No draft content generated for this tab.";
        viewer.innerHTML = highlightPlaceholders(rawText);
    }

    /** Highlight [PLACEHOLDER] tokens inside text */
    function highlightPlaceholders(text) {
        if (!text) return "";
        const escaped = escapeHtml(text);
        // Match tokens like [BUSINESS_NAME], [CONTACT_PERSON], [PLACEHOLDER: text], etc.
        const tokenRegex = /(\[[A-Za-z0-9_]+(?::\s*[^\]]+)?\])/g;
        return escaped.replace(tokenRegex, '<mark class="placeholder-mark" title="Action required: replace placeholder">$1</mark>');
    }

    /** Load recipients from /api/breach/<id>/recipients */
    async function loadRecipients(simId) {
        const tbody = document.getElementById("recipients-table-body");
        if (!tbody) return;

        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Loading recipient list...</td></tr>';

        try {
            const res = await fetch(`/api/breach/${simId}/recipients`);
            if (!res.ok) {
                throw new Error(`Failed to load recipients (${res.status})`);
            }
            const data = await res.json();
            const recipients = data.recipients || [];

            if (recipients.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No data principals identified in this breach blast-radius.</td></tr>';
                return;
            }

            tbody.innerHTML = "";
            recipients.forEach(r => {
                const tr = document.createElement("tr");

                const statusBadge = r.status === "confirmed"
                    ? '<span class="badge badge-success">&#x2714; Confirmed</span>'
                    : '<span class="badge badge-warning">&#x26A0; Possible</span>';

                const phoneBadge = (r.has_phone || r.phone_present === "yes")
                    ? '<span class="badge badge-success">Yes</span>'
                    : '<span class="badge badge-neutral">No</span>';

                const emailBadge = (r.has_email || r.email_present === "yes")
                    ? '<span class="badge badge-success">Yes</span>'
                    : '<span class="badge badge-neutral">No</span>';

                const principalLabel = r.masked_name
                    ? `${escapeHtml(r.label)} (${escapeHtml(r.masked_name)})`
                    : escapeHtml(r.label);

                tr.innerHTML = `
                    <td><strong>${principalLabel}</strong></td>
                    <td>${statusBadge}</td>
                    <td>${phoneBadge}</td>
                    <td>${emailBadge}</td>
                `;
                tbody.appendChild(tr);
            });
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Failed to load recipients: ${escapeHtml(err.message)}</td></tr>`;
        }
    }

})();
