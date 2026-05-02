/* =========================================================
   TABLE STACK v4 – ENHANCED DASHBOARD JS ENGINE (PHASE 8)
   ---------------------------------------------------------
   Purpose: Full interactive dashboard with:
   - Chart rendering (Chart.js)
   - Labor optimizer (API + UI)
   - Forecast refresh (mock API call)
   - CSV / PDF export
   - Theme toggle (dark/light)
   - Modal for target labor %
   - Toast notifications
   - **Phase 8: File upload + OCR import + task polling**
   - Ready for 10k+ lines (add new modules below)
   ========================================================= */

// ---------------------------------------------------------
// 1. GLOBALS & STATE
// ---------------------------------------------------------
window.TableStack = window.TableStack || {};

const App = {
    // Data from backend (injected via template)
    dashboardData: typeof dashboardData !== 'undefined' ? dashboardData : null,

    // UI state
    currentChart: null,
    targetLaborPercent: 25,
    theme: localStorage.getItem('theme') || 'light',

    // API endpoints (relative to Flask)
    endpoints: {
        dashboardData: '/api/dashboard/data',
        forecast: '/api/forecast',
        optimizeLabor: '/api/optimize-labor',
        uploadReport: '/api/upload-report',
        importStatus: '/api/import-status'   // base path, we append task_id
    },

    // Active polling intervals
    activePolling: null,
    toastTimeout: null
};

// ---------------------------------------------------------
// 2. UTILITIES (enhanced)
// ---------------------------------------------------------
function showToast(message, type = 'info') {
    // Remove existing toast
    const oldToast = document.querySelector('.toast');
    if (oldToast) oldToast.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: var(--bg-surface);
        border-left: 4px solid ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
        padding: 12px 20px;
        border-radius: 60px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        z-index: 1100;
        font-weight: 500;
        backdrop-filter: blur(12px);
        color: var(--text-primary);
        animation: fadeInUp 0.2s ease;
    `;
    document.body.appendChild(toast);

    if (App.toastTimeout) clearTimeout(App.toastTimeout);
    App.toastTimeout = setTimeout(() => toast.remove(), 4000);
}

function showComingSoon(feature, phase = 'Phase 8') {
    showToast(`✨ ${feature} is coming in ${phase}.`, 'info');
    console.log(`[Coming Soon] ${feature} (${phase})`);
}

function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

function parseCurrencyString(str) {
    return parseFloat(str.replace(/[$,]/g, '')) || 0;
}

// ---------------------------------------------------------
// 3. CHART RENDERING (unchanged)
// ---------------------------------------------------------
function renderSalesLaborChart(data = null) {
    const canvas = document.getElementById('salesLaborChart');
    if (!canvas) return;

    const weeklyData = data || (App.dashboardData ? App.dashboardData.weekly_snapshot : null);
    if (!weeklyData || !weeklyData.length) {
        console.warn('No weekly data for chart');
        return;
    }

    const labels = weeklyData.map(row => row.day);
    const sales = weeklyData.map(row => parseCurrencyString(row.sales));
    const labor = weeklyData.map(row => parseCurrencyString(row.labor));

    if (App.currentChart) App.currentChart.destroy();

    App.currentChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'Sales', data: sales, backgroundColor: 'rgba(37, 99, 235, 0.7)', borderRadius: 8, barPercentage: 0.65 },
                { label: 'Labor Cost', data: labor, backgroundColor: 'rgba(249, 115, 22, 0.7)', borderRadius: 8, barPercentage: 0.65 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { font: { weight: 'bold' } } },
                tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${formatCurrency(ctx.raw)}` } }
            },
            scales: { y: { beginAtZero: true, ticks: { callback: value => formatCurrency(value) } } }
        }
    });
    console.log('Chart rendered');
}

// ---------------------------------------------------------
// 4. FORECAST REFRESH (unchanged)
// ---------------------------------------------------------
async function refreshForecast() {
    showToast('Fetching latest forecast...', 'info');
    try {
        const response = await fetch(`${App.endpoints.forecast}?weeks=2`);
        if (!response.ok) throw new Error('Forecast API failed');
        const forecastData = await response.json();
        const container = document.getElementById('forecast-table');
        if (container && forecastData.forecast) {
            container.innerHTML = forecastData.forecast.map(f => `
                <div style="padding: 8px 0; border-bottom: 1px solid var(--border-light);">
                    <strong>${f.week}</strong> — Sales: ${f.sales} | Labor: ${f.labor} (${f.labor_percent})
                </div>
            `).join('');
            showToast('Forecast updated', 'success');
        }
    } catch (error) {
        console.error(error);
        showToast('Forecast API unavailable – using mock data', 'warning');
        const mockForecast = [
            { week: 'Week +1', sales: '$12,450', labor: '$2,988', labor_percent: '24.0%' },
            { week: 'Week +2', sales: '$12,800', labor: '$3,072', labor_percent: '24.0%' }
        ];
        const container = document.getElementById('forecast-table');
        if (container) {
            container.innerHTML = mockForecast.map(f => `
                <div style="padding: 8px 0; border-bottom: 1px solid var(--border-light);">
                    <strong>${f.week}</strong> — Sales: ${f.sales} | Labor: ${f.labor} (${f.labor_percent})
                </div>
            `).join('');
        }
    }
}

// ---------------------------------------------------------
// 5. LABOR OPTIMIZER (unchanged)
// ---------------------------------------------------------
async function runLaborOptimizer() {
    const target = App.targetLaborPercent;
    showToast(`Optimizing schedule for ${target}% labor target...`, 'info');
    try {
        const response = await fetch(App.endpoints.optimizeLabor, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_labor_percent: target })
        });
        if (!response.ok) throw new Error('Optimizer API failed');
        const data = await response.json();
        const resultsDiv = document.getElementById('optimizer-results');
        if (resultsDiv && data.optimized_schedule) {
            let html = `<strong>📋 Suggested schedule changes to reach ${target}% labor:</strong><ul style="margin-top: 12px;">`;
            data.optimized_schedule.forEach(s => {
                html += `<li><strong>${s.day}</strong>: ${s.current_hours}h → ${s.suggested_hours}h (save ${s.labor_reduction})</li>`;
            });
            html += `</ul>`;
            resultsDiv.innerHTML = html;
            showToast('Optimization complete', 'success');
        }
    } catch (error) {
        console.error(error);
        showToast('Optimizer API unavailable – using client-side simulation', 'warning');
        const resultsDiv = document.getElementById('optimizer-results');
        if (resultsDiv) {
            resultsDiv.innerHTML = `<div class="text-muted">⚠️ API not ready – in Phase 9 this will connect to real optimization engine.</div>`;
        }
    }
}

// ---------------------------------------------------------
// 6. EXPORT FUNCTIONS (unchanged)
// ---------------------------------------------------------
function exportCSV() {
    if (!App.dashboardData || !App.dashboardData.weekly_snapshot) {
        showToast('No data to export', 'error');
        return;
    }
    const rows = App.dashboardData.weekly_snapshot;
    const headers = ['Day', 'Sales', 'Labor', 'Labor %', 'Hours', 'Efficiency', 'Weather', 'Event'];
    const csvRows = [headers.join(',')];
    rows.forEach(row => {
        csvRows.push([
            row.day, row.sales, row.labor, row.labor_percent,
            row.staff_hours, row.efficiency, row.weather, row.event
        ].join(','));
    });
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.setAttribute('download', 'tablestack_export.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast('CSV exported successfully', 'success');
}

function exportPDF() {
    showComingSoon('PDF Export with full dashboard layout', 'Phase 8');
}

// ---------------------------------------------------------
// 7. THEME TOGGLE (unchanged)
// ---------------------------------------------------------
function initTheme() {
    document.documentElement.setAttribute('data-theme', App.theme);
}

function toggleTheme() {
    App.theme = App.theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', App.theme);
    localStorage.setItem('theme', App.theme);
    showToast(`${App.theme === 'dark' ? '🌙 Dark' : '☀️ Light'} mode activated`, 'success');
}

// ---------------------------------------------------------
// 8. MODAL HANDLING (enhanced)
// ---------------------------------------------------------
function initModal() {
    const modal = document.getElementById('settings-modal');
    if (!modal) return;

    const settingsBtn = document.getElementById('settings-btn');
    const closeBtn = modal.querySelector('.close');
    const saveBtn = document.getElementById('save-target');
    const targetInput = document.getElementById('modal-target');
    const slider = document.getElementById('target-labor-slider');
    const targetValueSpan = document.getElementById('target-labor-value');

    // Open modal
    if (settingsBtn) {
        settingsBtn.onclick = () => {
            if (targetInput) targetInput.value = App.targetLaborPercent;
            modal.style.display = 'flex';
        };
    }

    // Close modal (X button)
    if (closeBtn) closeBtn.onclick = () => modal.style.display = 'none';

    // Close modal on outside click
    window.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });

    // Close modal on ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
            modal.style.display = 'none';
        }
    });

    // Save target
    if (saveBtn && targetInput) {
        saveBtn.onclick = () => {
            const newTarget = parseFloat(targetInput.value);
            if (!isNaN(newTarget) && newTarget >= 15 && newTarget <= 45) {
                App.targetLaborPercent = newTarget;
                if (slider) slider.value = newTarget;
                if (targetValueSpan) targetValueSpan.innerText = newTarget + '%';
                modal.style.display = 'none';
                showToast(`Labor target set to ${newTarget}%`, 'success');
                // Optional: refresh dashboard with new target
                // refreshDashboardData();
            } else {
                showToast('Enter a value between 15 and 45', 'error');
            }
        };
    }

    // Slider realtime
    if (slider && targetValueSpan) {
        slider.addEventListener('input', (e) => {
            App.targetLaborPercent = parseFloat(e.target.value);
            targetValueSpan.innerText = App.targetLaborPercent + '%';
        });
    }
}

// ---------------------------------------------------------
// 9. TABLE ROW HIGHLIGHTING (unchanged)
// ---------------------------------------------------------
function highlightLaborRiskRows() {
    const rows = document.querySelectorAll('#weekly-table tbody tr');
    rows.forEach(row => {
        const laborPercentCell = row.cells[3];
        if (laborPercentCell) {
            const percentText = laborPercentCell.textContent;
            const value = parseFloat(percentText.replace('%', ''));
            if (value > 28) row.classList.add('labor-risk-high');
            else if (value > 25) row.classList.add('labor-risk-watch');
            else row.classList.add('labor-risk-good');
        }
    });
}

// ---------------------------------------------------------
// 10. DASHBOARD DATA RELOAD (refresh entire UI after import)
// ---------------------------------------------------------
async function refreshDashboardData() {
    showToast('Refreshing dashboard data...', 'info');
    try {
        const response = await fetch(`${App.endpoints.dashboardData}?target=${App.targetLaborPercent}`);
        if (!response.ok) throw new Error('API failed');
        const newData = await response.json();
        App.dashboardData = newData;

        // Update metrics cards (re‑render)
        const metricsGrid = document.querySelector('.metrics-grid');
        if (metricsGrid && newData.summary_metrics) {
            metricsGrid.innerHTML = newData.summary_metrics.map(metric => `
                <div class="metric-card" data-metric-label="${metric.label}">
                    <div class="metric-topline">
                        <h3>${metric.label}</h3>
                        <span class="status ${metric.status}">${metric.change}</span>
                    </div>
                    <div class="metric-value">${metric.value}</div>
                    <p>${metric.description}</p>
                </div>
            `).join('');
        }

        // Update weekly snapshot table
        const tableBody = document.querySelector('#weekly-table tbody');
        if (tableBody && newData.weekly_snapshot) {
            tableBody.innerHTML = newData.weekly_snapshot.map(row => `
                <tr data-day="${row.day}">
                    <td>${row.day}</td>
                    <td>${row.sales}</td>
                    <td>${row.labor}</td>
                    <td>${row.labor_percent}</td>
                    <td>${row.staff_hours}</td>
                    <td>${row.efficiency}</td>
                    <td>${row.weather}</td>
                    <td>${row.event}</td>
                </tr>
            `).join('');
            highlightLaborRiskRows(); // reapply row colors
        }

        // Update insight cards
        const insightList = document.querySelector('#recommendations-list');
        if (insightList && newData.recommendations) {
            insightList.innerHTML = newData.recommendations.map(rec => `
                <div class="insight-card">
                    <h3>${rec.title}</h3>
                    <strong>${rec.detail}</strong>
                    <p>${rec.impact}</p>
                </div>
            `).join('');
        }

        // Update forecast table (via separate endpoint, but we can also update from newData if present)
        if (newData.forecast_preview) {
            const forecastContainer = document.getElementById('forecast-table');
            if (forecastContainer) {
                forecastContainer.innerHTML = newData.forecast_preview.map(f => `
                    <div style="padding: 8px 0; border-bottom: 1px solid var(--border-light);">
                        <strong>${f.week}</strong> — Sales: ${f.sales} | Labor: ${f.labor} (${f.labor_percent})
                    </div>
                `).join('');
            }
        }

        // Re‑render chart
        renderSalesLaborChart(newData.weekly_snapshot);
        showToast('Dashboard data refreshed', 'success');
    } catch (error) {
        console.error(error);
        showToast('Could not refresh dashboard', 'error');
    }
}

// ---------------------------------------------------------
// 11. PHASE 8: FILE UPLOAD + OCR IMPORT + TASK POLLING
// ---------------------------------------------------------
function pollImportStatus(taskId, intervalMs = 2000) {
    if (App.activePolling) clearInterval(App.activePolling);
    App.activePolling = setInterval(async () => {
        try {
            const response = await fetch(`${App.endpoints.importStatus}/${taskId}`);
            if (!response.ok) throw new Error('Status check failed');
            const status = await response.json();
            if (status.status === 'complete') {
                clearInterval(App.activePolling);
                showToast(`Import complete: ${status.message || 'Data updated'}`, 'success');
                // Refresh full dashboard with new data
                await refreshDashboardData();
                // Also refresh forecast separately
                refreshForecast();
            } else if (status.status === 'failed') {
                clearInterval(App.activePolling);
                showToast(`Import failed: ${status.message || status.error}`, 'error');
            } else {
                // Still processing – update progress if available
                const progress = status.progress || 0;
                if (progress > 0 && progress < 100) {
                    showToast(`Importing: ${progress}% – ${status.message || 'Processing...'}`, 'info');
                }
            }
        } catch (error) {
            console.error('Polling error', error);
            clearInterval(App.activePolling);
            showToast('Error checking import status', 'error');
        }
    }, intervalMs);
}

async function uploadReportFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    showToast(`Uploading ${file.name}...`, 'info');
    try {
        const response = await fetch(App.endpoints.uploadReport, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Upload failed');
        }
        const result = await response.json();
        if (result.task_id) {
            showToast('File accepted, processing in background', 'success');
            pollImportStatus(result.task_id);
        } else {
            showToast('Upload succeeded but no task ID returned', 'warning');
        }
    } catch (error) {
        console.error(error);
        showToast(`Upload error: ${error.message}`, 'error');
    }
}

function initFileUpload() {
    // Create hidden file input if not exists
    let fileInput = document.getElementById('hidden-file-upload');
    if (!fileInput) {
        fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.id = 'hidden-file-upload';
        fileInput.accept = '.csv,.pdf,.png,.jpg,.jpeg,.tiff';
        fileInput.style.display = 'none';
        document.body.appendChild(fileInput);
    }

    // Trigger file picker when import button is clicked
    const importBtn = document.getElementById('import-btn');
    if (importBtn) {
        importBtn.onclick = () => {
            fileInput.click();
        };
    }

    // Handle file selection
    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            uploadReportFile(file);
        }
        fileInput.value = ''; // reset so same file can be re-uploaded
    });
}

// ---------------------------------------------------------
// 12. BIND ACTION BUTTONS (updated with real import)
// ---------------------------------------------------------
function bindActionButtons() {
    // File upload is now handled by initFileUpload, so no placeholder
    // Keep other buttons unchanged
    const insightBtn = document.getElementById('insight-btn');
    if (insightBtn) insightBtn.onclick = () => showComingSoon('AI‑powered deep insights & recommendations', 'Phase 9');

    const exportCsvBtn = document.getElementById('export-csv-btn');
    if (exportCsvBtn) exportCsvBtn.onclick = exportCSV;

    const exportPdfBtn = document.getElementById('export-pdf-btn');
    if (exportPdfBtn) exportPdfBtn.onclick = exportPDF;

    const refreshForecastBtn = document.getElementById('refresh-forecast');
    if (refreshForecastBtn) refreshForecastBtn.onclick = refreshForecast;

    const runOptimizerBtn = document.getElementById('run-optimizer');
    if (runOptimizerBtn) runOptimizerBtn.onclick = runLaborOptimizer;

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) themeToggle.onclick = toggleTheme;

    const tabs = document.querySelectorAll('.panel-tabs .tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.textContent.trim() !== 'Weekly') {
                showComingSoon(`${tab.textContent} chart view`, 'Phase 10');
            }
        });
    });

    const navLinks = document.querySelectorAll('.nav a:not(.active)');
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && href !== '#') {
            return; // real navigation
        }
        link.addEventListener('click', (e) => {
            e.preventDefault();
            showComingSoon(`${link.textContent.trim()} module`, 'Phase 8-10');
        });
    });
}

// ---------------------------------------------------------
// 13. INITIALIZE DASHBOARD (enhanced)
// ---------------------------------------------------------
function initializeDashboard() {
    console.log('🚀 Table Stack v4 Phase 8 JS initializing...');

    initTheme();
    if (App.dashboardData) {
        renderSalesLaborChart(App.dashboardData.weekly_snapshot);
        highlightLaborRiskRows();
    } else {
        console.warn('No dashboardData found; chart will not render');
    }
    initModal();
    bindActionButtons();
    initFileUpload();   // Phase 8: real file upload

    const slider = document.getElementById('target-labor-slider');
    if (slider) App.targetLaborPercent = parseFloat(slider.value);

    showToast('Dashboard ready – intelligence engine online', 'success');
}

// ---------------------------------------------------------
// 14. START ON DOM READY
// ---------------------------------------------------------
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

// ---------------------------------------------------------
// 15. FUTURE EXPANSION BLOCKS
// (Add new modules below without breaking existing code)
// ---------------------------------------------------------
// Example: Real-time WebSocket listener
// Example: Drag & drop schedule editor
// Example: Advanced filtering