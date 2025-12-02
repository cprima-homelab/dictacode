/**
 * Diagnostics page functionality (v0.3.0 Phase 3)
 */

(function() {
    'use strict';

    let diagnosticsData = {};

    /**
     * Run all diagnostics
     */
    window.runDiagnostics = async function() {
        const runBtn = document.getElementById('run-btn');
        const tbody = document.getElementById('diagnostics-body');

        runBtn.disabled = true;
        runBtn.textContent = '⏳ Running...';

        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">Running diagnostics...</td></tr>';

        try {
            // v0.3.4: API versioning - run diagnostics via POST /v1/api/diagnostics/run
            const response = await fetch('/v1/api/diagnostics/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await response.json();

            diagnosticsData = data || {};

            // Render results
            renderDiagnostics(diagnosticsData.checks || []);

        } catch (error) {
            console.error('Failed to run diagnostics:', error);
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--error); padding: 20px;">Failed to run diagnostics: ${error.message}</td></tr>`;
        } finally {
            runBtn.disabled = false;
            runBtn.textContent = '▶ Run All Checks';
        }
    };

    /**
     * Render diagnostics results
     */
    function renderDiagnostics(checks) {
        const tbody = document.getElementById('diagnostics-body');
        tbody.innerHTML = '';

        if (checks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--fg-dim); padding: 20px;">No diagnostics available</td></tr>';
            return;
        }

        checks.forEach(check => {
            const row = document.createElement('tr');

            // Name
            const nameCell = document.createElement('td');
            nameCell.textContent = check.name || check.check_name || 'Unknown';
            row.appendChild(nameCell);

            // Category
            const categoryCell = document.createElement('td');
            categoryCell.textContent = check.category || 'General';
            row.appendChild(categoryCell);

            // Result
            const resultCell = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = 'badge';

            const status = (check.status || check.result || '').toString().toLowerCase();
            if (status === 'ok' || status === 'pass' || status === 'passed' || status === 'healthy') {
                badge.classList.add('badge-ok');
                badge.textContent = '✓ OK';
            } else if (status === 'warning' || status === 'degraded') {
                badge.classList.add('badge-warning');
                badge.textContent = '⚠ Warning';
            } else {
                badge.classList.add('badge-error');
                badge.textContent = '✗ Failed';
            }

            resultCell.appendChild(badge);
            row.appendChild(resultCell);

            // Details button
            const actionsCell = document.createElement('td');
            const detailsBtn = document.createElement('button');
            detailsBtn.className = 'icon-btn';
            detailsBtn.textContent = '📋';
            detailsBtn.title = 'View details';
            detailsBtn.onclick = () => showDetails(check);
            actionsCell.appendChild(detailsBtn);
            row.appendChild(actionsCell);

            tbody.appendChild(row);
        });
    }

    /**
     * Show details in side drawer
     */
    function showDetails(check) {
        const drawer = document.getElementById('details-drawer');
        const title = document.getElementById('drawer-title');
        const content = document.getElementById('details-content');

        title.textContent = check.name || check.check_name || 'Check Details';

        // Format details
        let detailsText = '';

        if (check.message) {
            detailsText += `Message: ${check.message}\n\n`;
        }

        if (check.details) {
            detailsText += 'Details:\n';
            if (typeof check.details === 'string') {
                detailsText += check.details;
            } else {
                detailsText += JSON.stringify(check.details, null, 2);
            }
            detailsText += '\n\n';
        }

        if (check.metadata) {
            detailsText += 'Metadata:\n';
            detailsText += JSON.stringify(check.metadata, null, 2);
        }

        if (!detailsText) {
            detailsText = 'No additional details available.';
        }

        content.textContent = detailsText;

        // Show drawer
        drawer.removeAttribute('hidden');
    }

    /**
     * Close side drawer
     */
    window.closeDrawer = function() {
        const drawer = document.getElementById('details-drawer');
        drawer.setAttribute('hidden', '');
    };

    /**
     * Initialize diagnostics page
     */
    function init() {
        console.log('Diagnostics page initializing...');

        // Close drawer on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeDrawer();
            }
        });

        console.log('Diagnostics page initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
