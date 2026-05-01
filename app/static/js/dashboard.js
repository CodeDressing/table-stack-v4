/* =========================================================
   TABLE STACK v4 – ENHANCED DASHBOARD JS ENGINE
   ---------------------------------------------------------
   Purpose: Full interactive dashboard with:
   - Chart rendering (Chart.js)
   - Labor optimizer (API + UI)
   - Forecast refresh (mock API call)
   - CSV / PDF export
   - Theme toggle (dark/light)
   - Modal for target labor %
   - Toast notifications
   - Placeholder popups for unfinished features
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
        optimizeLabor: '/api/optimize-labor'
    },

    // Toast queue
    toastTimeout: null
};

// ---------------------------------------------------------
// 2. UTILITIES
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
    App.toastTimeout = setTimeout(() => toast.remove(), 3000);
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
// 3. CHART RENDERING (Sales vs Labor)
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
                {
                    label: 'Sales',
                    data: sales,
                    backgroundColor: 'rgba(37, 99, 235, 0.7)',
                    borderRadius: 8,
                    barPercentage: 0.65
                },
                {
                    label: 'Labor Cost',
                    data: labor,
                    backgroundColor: 'rgba(249, 115, 22, 0.7)',
                    borderRadius: 8,
                    barPercentage: 0.65
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { font: { weight: 'bold' } } },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${formatCurrency(context.raw)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) { return formatCurrency(value); }
                    }
                }
            }
        }
    });
    console.log('Chart rendered');
}

// ---------------------------------------------------------
// 4. FORECAST REFRESH (API call + mock fallback)
// ---------------------------------------------------------
async function refreshForecast() {
    showToast('Fetching latest forecast...', 'info');
    try {
        const response = await fetch(`${App.endpoints.forecast}?weeks=2`);
        if (!response.ok) throw new Error('Forecast API failed');
        const forecastData = await response.json();
        // Update forecast table in UI
        const container = document.getElementById('forecast-table');
        if (container && forecastData.length) {
            container.innerHTML = forecastData.map(f => `
                <div style="padding: 8px 0; border-bottom: 1px solid var(--border-light);">
                    <strong>${f.week}</strong> — Sales: ${f.sales} | Labor: ${f.labor} (${f.labor_percent})
                </div>
            `).join('');
            showToast('Forecast updated successfully', 'success');
        }
    } catch (error) {
        console.error(error);
        showToast('Forecast API unavailable – using mock data', 'warning');
        // Mock fallback
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
// 5. LABOR OPTIMIZER (call backend)
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
        // Fallback mock
        const resultsDiv = document.getElementById('optimizer-results');
        if (resultsDiv) {
            resultsDiv.innerHTML = `<div class="text-muted">⚠️ API not ready – in Phase 9 this will connect to real optimization engine.</div>`;
        }
    }
}

// ---------------------------------------------------------
// 6. EXPORT FUNCTIONS
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
    // In Phase 8: use html2canvas + jsPDF
}

// ---------------------------------------------------------
// 7. THEME TOGGLE (DARK / LIGHT)
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
// 8. MODAL HANDLING (Target Labor %)
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

    // Close modal
    if (closeBtn) closeBtn.onclick = () => modal.style.display = 'none';
    window.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };

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
                // Optionally re-fetch dashboard data with new target
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
// 9. TABLE ROW HIGHLIGHTING (Labor risk)
// ---------------------------------------------------------
function highlightLaborRiskRows() {
    const rows = document.querySelectorAll('#weekly-table tbody tr');
    rows.forEach(row => {
        const laborPercentCell = row.cells[3]; // Labor % column
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
// 10. BIND ACTION BUTTONS (with popups)
// ---------------------------------------------------------
function bindActionButtons() {
    // Import Report
    const importBtn = document.getElementById('import-btn');
    if (importBtn) importBtn.onclick = () => showComingSoon('OCR / File import with sales extraction', 'Phase 8');

    // Generate Insights (AI)
    const insightBtn = document.getElementById('insight-btn');
    if (insightBtn) insightBtn.onclick = () => showComingSoon('AI‑powered deep insights & recommendations', 'Phase 9');

    // Export CSV
    const exportCsvBtn = document.getElementById('export-csv-btn');
    if (exportCsvBtn) exportCsvBtn.onclick = exportCSV;

    // Export PDF
    const exportPdfBtn = document.getElementById('export-pdf-btn');
    if (exportPdfBtn) exportPdfBtn.onclick = exportPDF;

    // Refresh Forecast
    const refreshForecastBtn = document.getElementById('refresh-forecast');
    if (refreshForecastBtn) refreshForecastBtn.onclick = refreshForecast;

    // Run Optimizer
    const runOptimizerBtn = document.getElementById('run-optimizer');
    if (runOptimizerBtn) runOptimizerBtn.onclick = runLaborOptimizer;

    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) themeToggle.onclick = toggleTheme;

    // Chart Tabs (Weekly, Monthly, Forecast) – all coming soon except Weekly
    const tabs = document.querySelectorAll('.panel-tabs .tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.textContent.trim() !== 'Weekly') {
                showComingSoon(`${tab.textContent} chart view`, 'Phase 10');
            } else {
                // Already showing weekly – do nothing
            }
        });
    });

    // Sidebar nav links (Sales, Labor, Staffing, Reports, Forecast)
    const navLinks = document.querySelectorAll('.nav a:not(.active)');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            showComingSoon(`${link.textContent.trim()} module`, 'Phase 8-10');
        });
    });
}

// ---------------------------------------------------------
// 11. REFRESH DASHBOARD DATA (future use)
// ---------------------------------------------------------
async function refreshDashboardData() {
    showToast('Refreshing dashboard data...', 'info');
    try {
        const response = await fetch(App.endpoints.dashboardData);
        if (!response.ok) throw new Error('API failed');
        const newData = await response.json();
        App.dashboardData = newData;
        // Update UI: metrics, table, insights, etc. (simplified for demo)
        renderSalesLaborChart(newData.weekly_snapshot);
        showToast('Dashboard refreshed', 'success');
    } catch (error) {
        console.error(error);
        showToast('Could not refresh – using existing data', 'warning');
    }
}

// ---------------------------------------------------------
// 12. INITIALIZE DASHBOARD
// ---------------------------------------------------------
function initializeDashboard() {
    console.log('🚀 Table Stack v4 Enhanced JS initializing...');

    initTheme();
    if (App.dashboardData) {
        renderSalesLaborChart(App.dashboardData.weekly_snapshot);
        highlightLaborRiskRows();
    } else {
        console.warn('No dashboardData found; chart will not render');
    }
    initModal();
    bindActionButtons();

    // Set initial target labor from slider if present
    const slider = document.getElementById('target-labor-slider');
    if (slider) App.targetLaborPercent = parseFloat(slider.value);

    showToast('Dashboard ready – intelligence engine online', 'success');
}

// ---------------------------------------------------------
// 13. START ON DOM READY
// ---------------------------------------------------------
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

// ---------------------------------------------------------
// 14. FUTURE EXPANSION BLOCKS
// (Add new modules below without breaking existing code)
// ---------------------------------------------------------
// Example: Real-time WebSocket listener
// Example: Drag & drop schedule editor
// Example: Advanced filtering