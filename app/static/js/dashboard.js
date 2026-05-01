// Dashboard JS Engine
// -------------------
// This is the beginning of the frontend intelligence layer.

console.log("Dashboard JS initialized");


// -------------------------
// ACCESS BACKEND DATA
// -------------------------
function getWeeklyData() {
    return dashboardData.weekly_snapshot;
}


// -------------------------
// PREPARE CHART DATA
// -------------------------
function buildChartData() {
    const data = getWeeklyData();

    const labels = data.map(row => row.day);
    const sales = data.map(row => parseFloat(row.sales.replace(/[$,]/g, "")));
    const labor = data.map(row => parseFloat(row.labor.replace(/[$,]/g, "")));

    return { labels, sales, labor };
}


// -------------------------
// INITIALIZE CHART (PHASE 7 READY)
// -------------------------
function initChart() {
    const canvas = document.getElementById("salesLaborChart");

    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const chartData = buildChartData();

    // Placeholder rendering (no Chart.js yet)
    ctx.font = "16px Arial";
    ctx.fillText("Chart engine ready for integration...", 20, 50);

    console.log("Chart data:", chartData);
}


// -------------------------
// EVENT HANDLERS
// -------------------------
function bindUIActions() {

    const importBtn = document.getElementById("import-btn");
    const insightBtn = document.getElementById("insight-btn");

    if (importBtn) {
        importBtn.addEventListener("click", () => {
            alert("Import system coming in Phase 8 (OCR + file upload)");
        });
    }

    if (insightBtn) {
        insightBtn.addEventListener("click", () => {
            alert("AI insights engine coming in Phase 9");
        });
    }
}


// -------------------------
// BOOTSTRAP
// -------------------------
document.addEventListener("DOMContentLoaded", () => {
    console.log("Dashboard loaded");

    initChart();
    bindUIActions();
});