/**
 * Rights Desk Client-side Application (rights_desk.js)
 * Kavach DPDP Readiness Platform
 */

(function () {
  'use strict';

  // Global state for this page
  let _requests = [];
  let _ignoredMessages = [];
  let _liveTimers = [];

  document.addEventListener('DOMContentLoaded', () => {
    initRightsDesk();
  });

  function initRightsDesk() {
    const root = document.getElementById('rights-desk-root');
    if (!root) return;

    setupIntakePanel();
    setupIgnoredToggle();
    loadRequestsList();
  }

  // ---------------------------------------------------------------------------
  // Accessibility & Announcements
  // ---------------------------------------------------------------------------
  function announceStatus(message) {
    const el = document.getElementById('rd-status');
    if (el) {
      el.textContent = message;
    }
  }

  function showIntakeError(message) {
    const el = document.getElementById('intake-error');
    if (!el) return;
    if (message) {
      el.textContent = message;
      el.hidden = false;
    } else {
      el.hidden = true;
      el.textContent = '';
    }
  }

  // ---------------------------------------------------------------------------
  // Intake Panel setup
  // ---------------------------------------------------------------------------
  function setupIntakePanel() {
    const btnLoadDemo = document.getElementById('btn-load-demo');
    const btnDetect = document.getElementById('btn-detect');
    const btnScanDemo = document.getElementById('btn-scan-demo-rights');
    const textarea = document.getElementById('intake-textarea');

    if (btnLoadDemo) {
      btnLoadDemo.addEventListener('click', async () => {
        showIntakeError(null);
        btnLoadDemo.disabled = true;
        btnLoadDemo.textContent = 'Loading demo text...';
        try {
          const res = await fetch('/api/rights/demo-text');
          if (!res.ok) throw new Error('Failed to load demo requests text');
          const data = await res.json();
          if (textarea) textarea.value = data.text || '';
          announceStatus('Demo requests loaded into intake box.');
        } catch (err) {
          showIntakeError(err.message || 'Error loading demo text.');
        } finally {
          btnLoadDemo.disabled = false;
          btnLoadDemo.textContent = 'Load demo requests';
        }
      });
    }

    if (btnDetect) {
      btnDetect.addEventListener('click', async () => {
        showIntakeError(null);
        const text = textarea ? textarea.value.trim() : '';
        if (!text) {
          showIntakeError('Please paste a WhatsApp chat snippet or click "Load demo requests".');
          if (textarea) textarea.focus();
          return;
        }

        btnDetect.disabled = true;
        btnDetect.textContent = 'Detecting requests...';
        try {
          // Process intake
          const res = await fetch('/api/rights/intake', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Failed to detect requests');
          }
          const data = await res.json();

          // Identify ignored messages client-side by parsing chat lines
          await extractIgnoredMessages(text);

          announceStatus(`Intake complete: ${data.created || 0} requests detected.`);
          await loadRequestsList();
        } catch (err) {
          showIntakeError(err.message || 'Error detecting requests.');
        } finally {
          btnDetect.disabled = false;
          btnDetect.textContent = 'Detect requests';
        }
      });
    }

    if (btnScanDemo) {
      btnScanDemo.addEventListener('click', async () => {
        btnScanDemo.disabled = true;
        btnScanDemo.textContent = 'Scanning demo data...';
        try {
          // 1. Scan demo inventory
          const scanRes = await fetch('/api/scan-demo', { method: 'POST' });
          if (!scanRes.ok) throw new Error('Failed to scan demo dataset');

          // 2. Load demo text
          const demoRes = await fetch('/api/rights/demo-text');
          if (!demoRes.ok) throw new Error('Failed to load demo requests text');
          const demoData = await demoRes.json();
          if (textarea) textarea.value = demoData.text || '';

          // 3. Detect requests from demo text
          const intakeRes = await fetch('/api/rights/intake', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: demoData.text })
          });
          if (!intakeRes.ok) throw new Error('Failed to detect requests from demo text');
          const intakeData = await intakeRes.json();

          await extractIgnoredMessages(demoData.text);

          announceStatus(`Demo data scanned and ${intakeData.created || 0} requests detected.`);
          await loadRequestsList();
        } catch (err) {
          showIntakeError(err.message || 'Error scanning demo data.');
        } finally {
          btnScanDemo.disabled = false;
          btnScanDemo.textContent = 'Scan demo data & load demo requests';
        }
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Parse ignored messages
  // ---------------------------------------------------------------------------
  async function extractIgnoredMessages(rawText) {
    _ignoredMessages = [];
    const lines = rawText.split('\n');
    const waRegex = /^(\d{1,2}\/\d{1,2}\/\d{2,4},\s*\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(.+?):\s*(.+)$/i;

    const candidateMessages = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const m = waRegex.exec(trimmed);
      if (m) {
        candidateMessages.push({ sender: m[2].trim(), text: m[3].trim(), timestamp: m[1].trim() });
      }
    }

    for (const msg of candidateMessages) {
      try {
        const res = await fetch('/api/rights/classify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: msg.text })
        });
        if (res.ok) {
          const classification = await res.json();
          if (classification.intent === 'none') {
            _ignoredMessages.push({
              sender: msg.sender,
              text: msg.text,
              reason: classification.reason || 'No rights intent recognized'
            });
          }
        }
      } catch (e) {
        // Ignore classification fetch error for non-critical preview
      }
    }

    renderIgnoredMessages();
  }

  function setupIgnoredToggle() {
    const btnToggle = document.getElementById('btn-toggle-ignored');
    const list = document.getElementById('rd-ignored-list');
    if (!btnToggle || !list) return;

    btnToggle.addEventListener('click', () => {
      const isExpanded = btnToggle.getAttribute('aria-expanded') === 'true';
      btnToggle.setAttribute('aria-expanded', String(!isExpanded));
      list.hidden = isExpanded;
    });
  }

  function renderIgnoredMessages() {
    const section = document.getElementById('rd-ignored-section');
    const label = document.getElementById('rd-ignored-label');
    const list = document.getElementById('rd-ignored-list');
    if (!section || !label || !list) return;

    if (_ignoredMessages.length === 0) {
      section.hidden = true;
      list.innerHTML = '';
      return;
    }

    section.hidden = false;
    label.textContent = `Ignored messages (${_ignoredMessages.length})`;
    list.innerHTML = '';

    _ignoredMessages.forEach(msg => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="rd-ignored-sender">${escapeHtml(msg.sender)}: &ldquo;${escapeHtml(msg.text)}&rdquo;</span>
        <span class="rd-ignored-reason">Reason: ${escapeHtml(msg.reason)}</span>
      `;
      list.appendChild(li);
    });
  }

  // ---------------------------------------------------------------------------
  // Load & Render Requests
  // ---------------------------------------------------------------------------
  async function loadRequestsList() {
    const emptyState = document.getElementById('rd-empty-state');
    const countBadge = document.getElementById('requests-count');
    const listContainer = document.getElementById('rd-request-list');

    try {
      const res = await fetch('/api/rights/requests');
      if (!res.ok) throw new Error('Failed to fetch requests list');
      const data = await res.json();
      _requests = data.requests || [];

      if (countBadge) {
        countBadge.textContent = String(_requests.length);
      }

      if (_requests.length === 0) {
        if (emptyState) emptyState.hidden = false;
        if (listContainer) listContainer.innerHTML = '';
        return;
      }

      if (emptyState) emptyState.hidden = true;
      if (listContainer) {
        listContainer.innerHTML = '';
        clearLiveTimers();
        for (const req of _requests) {
          const card = await buildRequestCard(req);
          listContainer.appendChild(card);
        }
      }
    } catch (err) {
      showIntakeError(err.message || 'Error loading requests list.');
    }
  }

  function clearLiveTimers() {
    _liveTimers.forEach(id => clearInterval(id));
    _liveTimers = [];
  }

  // ---------------------------------------------------------------------------
  // Build a single Request Card
  // ---------------------------------------------------------------------------
  async function buildRequestCard(basicReq) {
    // Fetch full details via GET /api/rights/<id> (contains data_locations, countdown_seconds, etc.)
    let req = basicReq;
    try {
      const detailRes = await fetch(`/api/rights/${basicReq.id}`);
      if (detailRes.ok) {
        req = await detailRes.json();
      }
    } catch (e) {
      // Fallback to basicReq
    }

    const tpl = document.getElementById('tpl-request-card');
    const card = tpl.content.cloneNode(true).querySelector('.rd-req-card');
    card.id = `request-card-${req.id}`;
    card.setAttribute('aria-labelledby', `req-title-${req.id}`);

    // Intent badge
    const intentBadge = card.querySelector('.rd-intent-badge');
    const intentKey = (req.intent || 'none').toLowerCase();
    intentBadge.setAttribute('data-intent', intentKey);
    intentBadge.textContent = formatIntentLabel(req.intent);

    // Confidence
    const confEl = card.querySelector('.rd-confidence');
    if (req.confidence !== null && req.confidence !== undefined) {
      const pct = Math.round(req.confidence * 100);
      confEl.textContent = `${pct}% confidence`;
    }

    // Status badge
    const statusBadge = card.querySelector('.rd-status-badge');
    statusBadge.setAttribute('data-status', req.status || 'received');
    statusBadge.textContent = formatStatusLabel(req.status);

    // Reason
    const reasonEl = card.querySelector('.rd-reason');
    reasonEl.textContent = req.reason || `Classification: intent ${formatIntentLabel(req.intent)}`;

    // Excerpt
    const excerptEl = card.querySelector('.rd-excerpt');
    excerptEl.textContent = `"${req.message_excerpt_masked || ''}"`;

    // Person row
    const personLabel = card.querySelector('.rd-person-label');
    personLabel.id = `req-title-${req.id}`;
    personLabel.textContent = `Requester: ${req.sender_masked || '[Unknown]'}`;

    // Resolution badge
    const resBadge = card.querySelector('.rd-resolution-badge');
    resBadge.setAttribute('data-resolution', req.resolution || 'none');
    resBadge.textContent = formatResolutionLabel(req.resolution);

    // Live countdown to due_at
    const deadlineEl = card.querySelector('.rd-deadline');
    initCountdown(deadlineEl, req.due_at, req.countdown_seconds);

    // Data locations table
    const locDetails = card.querySelector('.rd-data-locations');
    const locTbody = card.querySelector('.rd-locations-table tbody');
    if (req.data_locations && req.data_locations.length > 0) {
      locDetails.hidden = false;
      locTbody.innerHTML = '';
      req.data_locations.forEach(loc => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${escapeHtml(loc.filename)}</strong></td>
          <td>${escapeHtml((loc.type || '').toUpperCase())}</td>
          <td>${loc.record_count} record${loc.record_count === 1 ? '' : 's'}</td>
        `;
        locTbody.appendChild(tr);
      });
    } else {
      locDetails.hidden = false;
      locTbody.innerHTML = '<tr><td colspan="3" class="text-muted">No personal records linked across indexed data sources.</td></tr>';
    }

    // Non-erase requests handling
    if (intentKey !== 'erase') {
      const nextStepPanel = card.querySelector('.rd-next-step');
      const nextStepText = card.querySelector('.rd-next-step-text');
      const closeBtn = card.querySelector('.rd-close-btn');

      nextStepPanel.hidden = false;
      nextStepText.innerHTML = `<strong>Suggested next step:</strong> ${getSuggestedNextStep(intentKey)}`;

      if (req.status === 'rejected') {
        closeBtn.disabled = true;
        closeBtn.textContent = 'Closed';
      } else {
        closeBtn.addEventListener('click', async () => {
          closeBtn.disabled = true;
          closeBtn.textContent = 'Closing...';
          try {
            const r = await fetch(`/api/rights/${req.id}/reject`, { method: 'POST' });
            if (!r.ok) throw new Error('Failed to close request');
            statusBadge.setAttribute('data-status', 'rejected');
            statusBadge.textContent = 'Closed';
            closeBtn.textContent = 'Closed';
            announceStatus(`Request #${req.id} marked closed.`);
          } catch (err) {
            alert(err.message || 'Error closing request');
            closeBtn.disabled = false;
            closeBtn.textContent = 'Close / Mark handled';
          }
        });
      }
    } else {
      // Erase stepper
      const stepper = card.querySelector('.rd-stepper');
      stepper.hidden = false;
      setupEraseStepper(card, req);
    }

    return card;
  }

  // ---------------------------------------------------------------------------
  // Erase Workflow Stepper (Steps 1 -> 2 -> 3 -> 4)
  // ---------------------------------------------------------------------------
  function setupEraseStepper(card, req) {
    const step1 = card.querySelector('.rd-step[data-step="1"]');
    const step2 = card.querySelector('.rd-step[data-step="2"]');
    const step3 = card.querySelector('.rd-step[data-step="3"]');
    const step4 = card.querySelector('.rd-step[data-step="4"]');

    // Step 1 controls
    const chkIdentity = step1.querySelector('.rd-chk-identity');
    const btnConfirmId = step1.querySelector('.rd-btn-confirm-identity');

    chkIdentity.addEventListener('change', () => {
      btnConfirmId.disabled = !chkIdentity.checked;
    });

    btnConfirmId.addEventListener('click', async () => {
      btnConfirmId.disabled = true;
      btnConfirmId.textContent = 'Verifying & building plan...';
      try {
        // 1. Confirm identity
        const confirmRes = await fetch(`/api/rights/${req.id}/confirm-identity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ detail: 'matched' })
        });
        if (!confirmRes.ok) {
          const e = await confirmRes.json().catch(() => ({}));
          throw new Error(e.error || 'Identity confirmation failed');
        }

        // 2. Build erasure plan
        const planRes = await fetch(`/api/rights/requests/${req.id}/plan`, {
          method: 'POST'
        });
        if (!planRes.ok) {
          const e = await planRes.json().catch(() => ({}));
          throw new Error(e.error || 'Failed to build erasure plan');
        }
        const planData = await planRes.json();

        // Update card status
        const statusBadge = card.querySelector('.rd-status-badge');
        statusBadge.setAttribute('data-status', 'plan_ready');
        statusBadge.textContent = 'Plan ready';

        const resBadge = card.querySelector('.rd-resolution-badge');
        resBadge.setAttribute('data-resolution', 'strong');
        resBadge.textContent = 'Strong match (verified)';

        // Advance to Step 2
        chkIdentity.disabled = true;
        step1.setAttribute('data-active', 'false');
        renderStep2(card, req.id, planData.plan, planData.plan_hash);
        announceStatus(`Identity verified and erasure plan built for request #${req.id}.`);
      } catch (err) {
        alert(err.message || 'Error confirming identity');
        btnConfirmId.disabled = false;
        btnConfirmId.textContent = 'Confirm identity & build plan';
      }
    });

    // Check current state to determine which step to display
    if (req.status === 'executed') {
      chkIdentity.checked = true;
      chkIdentity.disabled = true;
      step1.hidden = false;
      step1.setAttribute('data-active', 'false');
      step2.hidden = true;
      step3.hidden = true;
      renderStep4(card, req.id);
    } else if (req.status === 'approved') {
      chkIdentity.checked = true;
      chkIdentity.disabled = true;
      step1.hidden = false;
      step1.setAttribute('data-active', 'false');
      renderStep3(card, req.id, req.plan_hash, req.plan_json ? JSON.parse(req.plan_json).counts : null);
    } else if (req.status === 'plan_ready' && req.plan_json) {
      chkIdentity.checked = true;
      chkIdentity.disabled = true;
      step1.hidden = false;
      step1.setAttribute('data-active', 'false');
      renderStep2(card, req.id, JSON.parse(req.plan_json), req.plan_hash);
    } else {
      // Step 1 is active
      step1.setAttribute('data-active', 'true');
    }
  }

  // ---------------------------------------------------------------------------
  // Step 2: Review Plan
  // ---------------------------------------------------------------------------
  function renderStep2(card, requestId, plan, planHash) {
    const step2 = card.querySelector('.rd-step[data-step="2"]');
    const planBody = step2.querySelector('.rd-plan-body');
    const btnApprove = step2.querySelector('.rd-btn-approve');

    step2.hidden = false;
    step2.setAttribute('data-active', 'true');

    // Build grouped plan tables per source
    let html = '';
    const sources = plan.sources || {};

    Object.keys(sources).forEach(sourceName => {
      const sourceInfo = sources[sourceName];
      html += `<div class="rd-plan-source-block">`;
      html += `<h4 class="rd-plan-source-title">📁 Source: ${escapeHtml(sourceName)} (${escapeHtml((sourceInfo.type || '').toUpperCase())})</h4>`;
      html += `
        <table class="rd-table rd-plan-table">
          <thead>
            <tr>
              <th scope="col">Record</th>
              <th scope="col">Field / Header</th>
              <th scope="col">Decision</th>
              <th scope="col">Reason Code</th>
              <th scope="col">Legal Basis / Citation</th>
              <th scope="col">Override</th>
            </tr>
          </thead>
          <tbody>
      `;

      const records = sourceInfo.records || {};
      Object.keys(records).forEach(recordKey => {
        const record = records[recordKey];
        const fields = record.fields || {};

        Object.keys(fields).forEach(fieldKey => {
          const f = fields[fieldKey];
          const verifyChip = f.verify ? `<span class="rd-verify-chip" title="Requires human/legal verification">verify</span>` : '';

          html += `
            <tr data-record-key="${escapeHtml(recordKey)}" data-field="${escapeHtml(fieldKey)}">
              <td><code>${escapeHtml(recordKey)}</code></td>
              <td><strong>${escapeHtml(fieldKey)}</strong></td>
              <td>
                <span class="rd-decision-badge" data-d="${escapeHtml(f.decision)}">${escapeHtml(f.decision)}</span>
              </td>
              <td><code>${escapeHtml(f.reason_code || '')}</code></td>
              <td>${escapeHtml(f.citation_hint || '')} ${verifyChip}</td>
              <td>
                <select class="rd-override-select" aria-label="Override decision for ${escapeHtml(fieldKey)} in ${escapeHtml(recordKey)}">
                  <option value="ERASE" ${f.decision === 'ERASE' ? 'selected' : ''}>ERASE</option>
                  <option value="MASK" ${f.decision === 'MASK' ? 'selected' : ''}>MASK</option>
                  <option value="RETAIN" ${f.decision === 'RETAIN' ? 'selected' : ''}>RETAIN</option>
                  <option value="REVIEW" ${f.decision === 'REVIEW' ? 'selected' : ''}>REVIEW</option>
                </select>
              </td>
            </tr>
          `;
        });
      });

      html += `</tbody></table></div>`;
    });

    planBody.innerHTML = html;

    // Attach override event listeners to select elements
    planBody.querySelectorAll('.rd-override-select').forEach(select => {
      select.addEventListener('change', async (e) => {
        const tr = select.closest('tr');
        const recordKey = tr.getAttribute('data-record-key');
        const fieldKey = tr.getAttribute('data-field');
        const newDecision = select.value;

        select.disabled = true;
        try {
          const res = await fetch(`/api/rights/${requestId}/plan-override`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              record_key: recordKey,
              field: fieldKey,
              decision: newDecision
            })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Failed to update plan override');
          }
          const data = await res.json();
          // Update the decision badge in the row
          const badge = tr.querySelector('.rd-decision-badge');
          if (badge) {
            badge.setAttribute('data-d', newDecision);
            badge.textContent = newDecision;
          }
          planHash = data.plan_hash;
          plan.counts = data.counts;
          announceStatus(`Decision for ${fieldKey} overridden to ${newDecision}.`);
        } catch (err) {
          alert(err.message || 'Error updating override');
        } finally {
          select.disabled = false;
        }
      });
    });

    // Approve Plan button
    btnApprove.onclick = async () => {
      btnApprove.disabled = true;
      btnApprove.textContent = 'Approving plan...';
      try {
        const res = await fetch(`/api/rights/requests/${requestId}/approve`, {
          method: 'POST'
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || 'Failed to approve plan');
        }

        const statusBadge = card.querySelector('.rd-status-badge');
        statusBadge.setAttribute('data-status', 'approved');
        statusBadge.textContent = 'Approved';

        step2.setAttribute('data-active', 'false');
        renderStep3(card, requestId, planHash, plan.counts);
        announceStatus(`Erasure plan approved for request #${requestId}. Ready to execute.`);
      } catch (err) {
        alert(err.message || 'Error approving plan');
        btnApprove.disabled = false;
        btnApprove.textContent = 'Approve plan';
      }
    };
  }

  // ---------------------------------------------------------------------------
  // Step 3: Approve & Run
  // ---------------------------------------------------------------------------
  function renderStep3(card, requestId, planHash, counts) {
    const step3 = card.querySelector('.rd-step[data-step="3"]');
    const hashDisplay = step3.querySelector('.rd-plan-hash-display');
    const countsDisplay = step3.querySelector('.rd-confirm-counts');
    const btnExecute = step3.querySelector('.rd-btn-execute');

    step3.hidden = false;
    step3.setAttribute('data-active', 'true');

    // Short form hash
    const shortHash = planHash ? `${planHash.substring(0, 10)}...${planHash.substring(planHash.length - 8)}` : '[pending]';
    hashDisplay.innerHTML = `<strong>Plan SHA-256 Hash:</strong> <code title="${escapeHtml(planHash || '')}">${escapeHtml(shortHash)}</code>`;

    // Counts dialog
    const eraseCount = counts ? (counts.ERASE || 0) : 0;
    const maskCount = counts ? (counts.MASK || 0) : 0;
    const retainCount = counts ? (counts.RETAIN || 0) : 0;
    const reviewCount = counts ? (counts.REVIEW || 0) : 0;

    countsDisplay.innerHTML = `
      Please confirm execution. The following actions will be performed:
      <strong>${eraseCount} fields to ERASE</strong>,
      <strong>${maskCount} fields to MASK</strong>,
      <strong>${retainCount + reviewCount} fields to RETAIN</strong>.
      Original files are protected; cleaned copies will be produced in the output directory.
    `;

    btnExecute.onclick = async () => {
      const confirmed = window.confirm(
        `Are you sure you want to execute erasure for Request #${requestId}?\n` +
        `Actions: ${eraseCount} erase, ${maskCount} mask, ${retainCount + reviewCount} retain.`
      );
      if (!confirmed) return;

      btnExecute.disabled = true;
      btnExecute.textContent = 'Executing erasure...';
      try {
        const res = await fetch(`/api/rights/requests/${requestId}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirm_hash: planHash })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || 'Erasure execution failed');
        }
        const data = await res.json();

        const statusBadge = card.querySelector('.rd-status-badge');
        statusBadge.setAttribute('data-status', 'executed');
        statusBadge.textContent = 'Executed';

        step3.setAttribute('data-active', 'false');
        step3.hidden = true;
        renderStep4(card, requestId, data.receipt);
        announceStatus(`Erasure executed successfully for request #${requestId}.`);
      } catch (err) {
        alert(err.message || 'Error executing erasure');
        btnExecute.disabled = false;
        btnExecute.textContent = 'Execute erasure';
      }
    };
  }

  // ---------------------------------------------------------------------------
  // Step 4: Result View
  // ---------------------------------------------------------------------------
  async function renderStep4(card, requestId, passedReceipt) {
    const step4 = card.querySelector('.rd-step[data-step="4"]');
    const resultBody = step4.querySelector('.rd-result-body');

    step4.hidden = false;
    step4.setAttribute('data-active', 'true');

    let receipt = passedReceipt;
    if (!receipt) {
      resultBody.innerHTML = '<p class="text-muted">Loading execution receipt...</p>';
      try {
        const res = await fetch(`/api/rights/${requestId}/receipt`);
        if (!res.ok) throw new Error('Failed to load receipt');
        receipt = await res.json();
      } catch (err) {
        resultBody.innerHTML = `<p class="rd-inline-error">Error loading receipt: ${escapeHtml(err.message)}</p>`;
        return;
      }
    }

    // Compute residual counts
    let totalUnexpected = 0;
    const residualReport = receipt.residual_report || {};
    Object.keys(residualReport).forEach(filename => {
      const rep = residualReport[filename];
      if (rep) {
        ['phones', 'emails', 'aadhaar', 'names'].forEach(cat => {
          if (rep[cat] && rep[cat].unexpected) {
            totalUnexpected += rep[cat].unexpected;
          }
        });
      }
    });

    const actionCounts = receipt.action_counts || {};
    const retainedItems = receipt.retained_items || [];

    // Retained items table
    let retainedTableHtml = '';
    if (retainedItems.length > 0) {
      retainedTableHtml = `
        <h4 class="rd-plan-source-title mt-3">Expected Retained Items &amp; Justifications</h4>
        <table class="rd-table">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Record</th>
              <th scope="col">Field</th>
              <th scope="col">Reason Code</th>
              <th scope="col">Legal Justification / Citation</th>
            </tr>
          </thead>
          <tbody>
            ${retainedItems.map(item => `
              <tr>
                <td><strong>${escapeHtml(item.source)}</strong></td>
                <td><code>${escapeHtml(item.record_key)}</code></td>
                <td>${escapeHtml(item.field)}</td>
                <td><code>${escapeHtml(item.reason_code)}</code></td>
                <td>${escapeHtml(item.citation_hint || 'Retention required by law')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    // Build the complete result HTML
    resultBody.innerHTML = `
      <div class="rd-result-grid">
        <div class="rd-result-stat">
          <span class="rd-result-stat-value" style="color:#991b1b">${actionCounts.ERASE || 0}</span>
          <span class="rd-result-stat-label">Fields Erased</span>
        </div>
        <div class="rd-result-stat">
          <span class="rd-result-stat-value" style="color:#854d0e">${actionCounts.MASK || 0}</span>
          <span class="rd-result-stat-label">Fields Masked</span>
        </div>
        <div class="rd-result-stat">
          <span class="rd-result-stat-value" style="color:#166534">${actionCounts.RETAIN || 0}</span>
          <span class="rd-result-stat-label">Fields Retained</span>
        </div>
      </div>

      <!-- Residual Check Panel -->
      <div class="rd-residual-panel" role="region" aria-label="Residual Scan Check">
        <div class="rd-residual-title">
          ${totalUnexpected === 0
            ? '<span aria-hidden="true">✅</span> <strong>Post-Erasure Residual Check: Passed</strong>'
            : '<span aria-hidden="true">⚠️</span> <strong>Post-Erasure Residual Check: Warning</strong>'}
        </div>
        <p class="mb-0">
          Unexpected residual identifiers: <strong>${totalUnexpected}</strong>.
          ${totalUnexpected === 0 ? 'No unexpected PII remains in cleaned copies.' : 'Review retained items below for potential residual matches.'}
        </p>
      </div>

      <!-- Retained items with reasons -->
      ${retainedTableHtml}

      <!-- Mandatory Legal & Processor note -->
      <div class="rd-retained-note mt-3" role="note">
        <strong>Important:</strong> Backups and copies held by processors are outside this tool.
        If customer data was shared with diagnostic labs, cloud platforms, or third parties, notify them directly.
      </div>

      <!-- Actions: View Receipt + Download ZIP -->
      <div class="rd-result-actions">
        <button type="button" class="btn btn-secondary rd-btn-view-receipt">
          View receipt
        </button>
        <a href="/api/rights/${requestId}/download" class="btn btn-primary" download>
          Download cleaned files + receipt (.zip)
        </a>
      </div>

      <!-- Expandable Receipt JSON Viewer -->
      <div class="rd-receipt-viewer mt-3" hidden>
        <h5 class="rd-plan-source-title">Receipt Details (#${requestId})</h5>
        <pre class="rd-excerpt" style="max-height:260px; overflow-y:auto;"><code>${escapeHtml(JSON.stringify(receipt, null, 2))}</code></pre>
      </div>
    `;

    // Hook up view receipt button
    const btnViewReceipt = resultBody.querySelector('.rd-btn-view-receipt');
    const viewer = resultBody.querySelector('.rd-receipt-viewer');
    if (btnViewReceipt && viewer) {
      btnViewReceipt.addEventListener('click', () => {
        viewer.hidden = !viewer.hidden;
        btnViewReceipt.textContent = viewer.hidden ? 'View receipt' : 'Hide receipt';
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Countdown Timer
  // ---------------------------------------------------------------------------
  function initCountdown(el, dueAtStr, initialSeconds) {
    if (!el || !dueAtStr) return;

    function update() {
      const now = new Date();
      const due = new Date(dueAtStr);
      const diffMs = due.getTime() - now.getTime();

      if (isNaN(diffMs)) {
        el.textContent = 'Due date pending';
        return;
      }

      if (diffMs <= 0) {
        el.textContent = 'Overdue';
        el.className = 'rd-deadline urgent';
        return;
      }

      const totalSeconds = Math.floor(diffMs / 1000);
      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);

      if (days > 1) {
        el.textContent = `${days} days left`;
      } else if (days === 1) {
        el.textContent = `1 day, ${hours}h left`;
        el.className = 'rd-deadline warning';
      } else {
        el.textContent = `${hours}h left (due today)`;
        el.className = 'rd-deadline urgent';
      }
    }

    update();
    const timerId = setInterval(update, 60000);
    _liveTimers.push(timerId);
  }

  // ---------------------------------------------------------------------------
  // Formatting Helpers
  // ---------------------------------------------------------------------------
  function formatIntentLabel(intent) {
    if (!intent) return 'UNKNOWN';
    switch (intent.toLowerCase()) {
      case 'erase': return 'ERASE';
      case 'access': return 'ACCESS';
      case 'correct': return 'CORRECT';
      case 'withdraw_consent': return 'WITHDRAW CONSENT';
      case 'complaint': return 'COMPLAINT';
      case 'none': return 'NONE';
      default: return intent.toUpperCase();
    }
  }

  function formatStatusLabel(status) {
    if (!status) return 'Received';
    switch (status.toLowerCase()) {
      case 'received': return 'Received';
      case 'identity_pending': return 'Identity pending';
      case 'plan_ready': return 'Plan ready';
      case 'approved': return 'Approved';
      case 'executed': return 'Executed';
      case 'rejected': return 'Closed';
      default: return status.charAt(0).toUpperCase() + status.slice(1);
    }
  }

  function formatResolutionLabel(res) {
    if (!res) return 'Unmatched';
    switch (res.toLowerCase()) {
      case 'strong': return 'Strong match';
      case 'probable': return 'Probable match';
      case 'ambiguous': return 'Ambiguous match';
      case 'none': return 'No match';
      default: return res;
    }
  }

  function getSuggestedNextStep(intent) {
    switch (intent) {
      case 'access':
        return 'Export the data principal\'s records across data sources into a portable summary and provide it within 30 days.';
      case 'correct':
        return 'Verify the requested correction against identity documents and update the corresponding source records.';
      case 'withdraw_consent':
        return 'Cease processing activities dependent on consent, unless retention is required by another applicable statutory law.';
      case 'complaint':
        return 'Acknowledge receipt within standard timelines, investigate the grievance, and respond with findings and resolution.';
      default:
        return 'Review request details and consult DPDP guidelines.';
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

})();
