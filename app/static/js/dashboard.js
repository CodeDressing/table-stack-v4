/* =========================================================
   TABLE STACK v4 DASHBOARD JS ENGINE
   Purpose:
   - Render Chart.js dashboard visuals
   - Power buttons and frontend interactions
   - Keep JS organized for future large module upgrades
   ========================================================= */


/* =========================================================
   1. APP STATE + SAFETY CHECKS
   ========================================================= */

console.log("Dashboard JS initialized");

const TableStackDashboard = {
    data: window.dashboardData || {},
    charts: {},
    settings: {
        laborTargetPercent: 25,
        currencyLocale: "en-US",
        currencyCode: "USD"
    }
};

function hasDashboardData() {
    return Boolean(
        TableStackDashboard.data &&
        TableStackDashboard.data.weekly_snapshot &&
        Array.isArray(TableStackDashboard.data.weekly_snapshot)
    );
}


/* =========================================================
   2. DATA HELPERS
   ========================================================= */

function getWeeklyData() {
    if (!hasDashboardData()) {
        console.warn("Dashboard weekly data is missing or invalid.");
        return [];
    }

    return TableStackDashboard.data.weekly_snapshot;
}

function parseCurrency(value) {
    return Number(String(value).replace(/[$,]/g, "")) || 0;
}

function parsePercentage(value) {
    return Number(String(value).replace("%", "")) || 0;
}

function formatCurrency(value) {
    return new Intl.NumberFormat(TableStackDashboard.settings.currencyLocale, {
        style: "currency",
        currency: TableStackDashboard.settings.currencyCode,
        maximumFractionDigits: 0
    }).format(value);
}


/* =========================================================
   3. CHART DATA BUILDERS
   ========================================================= */

function buildSalesLaborChartData() {
    const weeklyData = getWeeklyData();

    return {
        labels: weeklyData.map(row => row.day),
        sales: weeklyData.map(row => parseCurrency(row.sales)),
        labor: weeklyData.map(row => parseCurrency(row.labor)),
        laborPercent: weeklyData.map(row => parsePercentage(row.labor_percent))
    };
}


/* =========================================================
   4. CHART RENDERING
   ========================================================= */

function renderSalesLaborChart() {
    const canvas = document.getElementById("salesLaborChart");

    if (!canvas) {
        console.warn("salesLaborChart canvas not found.");
        return;
    }

    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded. Check dashboard.html CDN script.");
        return;
    }

    const chartData = buildSalesLaborChartData();

    if (TableStackDashboard.charts.salesLabor) {
        TableStackDashboard.charts.salesLabor.destroy();
    }

    TableStackDashboard.charts.salesLabor = new Chart(canvas, {
        type: "bar",
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    label: "Sales",
                    data: chartData.sales,
                    borderWidth: 1,
                    borderRadius: 10
                },
                {
                    label: "Labor Cost",
                    data: chartData.labor,
                    borderWidth: 1,
                    borderRadius: 10
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        font: {
                            weight: "bold"
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${formatCurrency(context.raw)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            weight: "bold"
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });

    console.log("Sales/Labor chart rendered:", chartData);
}


/* =========================================================
   5. TABLE ENHANCEMENTS
   ========================================================= */

function highlightLaborRiskRows() {
    const rows = document.querySelectorAll("#weekly-table tbody tr");

    rows.forEach(row => {
        const laborPercentCell = row.children[3];

        if (!laborPercentCell) return;

        const laborPercent = parsePercentage(laborPercentCell.textContent);

        if (laborPercent > 28) {
            row.classList.add("labor-risk-high");
        } else if (laborPercent > TableStackDashboard.settings.laborTargetPercent) {
            row.classList.add("labor-risk-watch");
        } else {
            row.classList.add("labor-risk-good");
        }
    });
}

function exportWeeklyTableToCsv() {
    const rows = getWeeklyData();

    if (!rows.length) {
        alert("No weekly data available to export.");
        return;
    }

    const headers = ["Day", "Sales", "Labor", "Labor Percent"];
    const csvRows = [headers.join(",")];

    rows.forEach(row => {
        csvRows.push([
            row.day,
            row.sales,
            row.labor,
            row.labor_percent
        ].join(","));
    });

    const csvContent = csvRows.join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const downloadLink = document.createElement("a");
    downloadLink.href = url;
    downloadLink.download = "table-stack-weekly-performance.csv";
    downloadLink.click();

    URL.revokeObjectURL(url);
}


/* =========================================================
   6. UI ACTIONS
   ========================================================= */

function showComingSoonAlert(featureName, phaseLabel) {
    alert(`${featureName} is planned for ${phaseLabel}.`);
}

function bindHeaderActions() {
    const importBtn = document.getElementById("import-btn");
    const insightBtn = document.getElementById("insight-btn");

    if (importBtn) {
        importBtn.addEventListener("click", () => {
            showComingSoonAlert("Report import with OCR/file upload", "Phase 8");
        });
    }

    if (insightBtn) {
        insightBtn.addEventListener("click", () => {
            showComingSoonAlert("AI-powered operational insights", "Phase 9");
        });
    }
}

function bindExportActions() {
    const exportButtons = document.querySelectorAll(".ghost-button");

    exportButtons.forEach(button => {
        if (button.textContent.trim().toLowerCase().includes("export")) {
            button.addEventListener("click", exportWeeklyTableToCsv);
        }
    });
}

function bindChartTabs() {
    const tabs = document.querySelectorAll(".panel-tabs .tab");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(item => item.classList.remove("active"));
            tab.classList.add("active");

            const selectedView = tab.textContent.trim();

            if (selectedView !== "Weekly") {
                showComingSoonAlert(`${selectedView} chart view`, "a future analytics expansion");
            }
        });
    });
}


/* =========================================================
   7. DASHBOARD DIAGNOSTICS
   ========================================================= */

function logDashboardSummary() {
    const weeklyData = getWeeklyData();

    const totalSales = weeklyData.reduce((total, row) => {
        return total + parseCurrency(row.sales);
    }, 0);

    const totalLabor = weeklyData.reduce((total, row) => {
        return total + parseCurrency(row.labor);
    }, 0);

    const laborPercent = totalSales > 0 ? (totalLabor / totalSales) * 100 : 0;

    console.log("Dashboard diagnostics:", {
        daysLoaded: weeklyData.length,
        totalSales,
        totalLabor,
        laborPercent: `${laborPercent.toFixed(1)}%`
    });
}


/* =========================================================
   8. BOOTSTRAP
   ========================================================= */

function initializeDashboard() {
    console.log("Dashboard loaded");

    renderSalesLaborChart();
    highlightLaborRiskRows();
    bindHeaderActions();
    bindExportActions();
    bindChartTabs();
    logDashboardSummary();
}

document.addEventListener("DOMContentLoaded", initializeDashboard);