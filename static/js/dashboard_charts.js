const chartState = {
  line: null,
  expenseDonut: null,
  incomeDonut: null,
};

const getJson = (id) => {
  const el = document.getElementById(id);
  if (!el) return null;
  try {
    return JSON.parse(el.textContent);
  } catch (error) {
    console.error("Erro ao ler JSON do chart:", error);
    return null;
  }
};

const renderCharts = () => {
  if (typeof Chart === "undefined") return;

  const lineData = getJson("line-chart-data");
  const expenseData = getJson("expense-chart-data");
  const incomeData = getJson("income-chart-data");

  const lineCanvas = document.getElementById("expenseLineChart");
  const expenseCanvas = document.getElementById("expenseDonutChart");
  const incomeCanvas = document.getElementById("incomeDonutChart");

  if (lineCanvas && lineData) {
    chartState.line?.destroy();
    chartState.line = new Chart(lineCanvas, {
      type: "line",
      data: {
        labels: lineData.labels,
        datasets: [
          {
            label: "Despesa acumulada",
            data: lineData.data,
            borderColor: "#4c7dff",
            backgroundColor: "rgba(76, 125, 255, 0.2)",
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: { grid: { display: false } },
        },
      },
    });
  }

  if (expenseCanvas && expenseData) {
    chartState.expenseDonut?.destroy();
    chartState.expenseDonut = new Chart(expenseCanvas, {
      type: "doughnut",
      data: {
        labels: expenseData.labels,
        datasets: [
          {
            data: expenseData.data,
            backgroundColor: [
              "#4c7dff",
              "#22c55e",
              "#f97316",
              "#06b6d4",
              "#a855f7",
              "#f43f5e",
              "#64748b",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  if (incomeCanvas && incomeData) {
    chartState.incomeDonut?.destroy();
    chartState.incomeDonut = new Chart(incomeCanvas, {
      type: "doughnut",
      data: {
        labels: incomeData.labels,
        datasets: [
          {
            data: incomeData.data,
            backgroundColor: [
              "#22c55e",
              "#4c7dff",
              "#f59e0b",
              "#14b8a6",
              "#8b5cf6",
              "#e11d48",
              "#64748b",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    });
  }
};

document.addEventListener("DOMContentLoaded", renderCharts);

document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target && event.detail.target.id === "dashboard-content") {
    renderCharts();
  }
});
