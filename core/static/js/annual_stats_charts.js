(() => {
  const charts = {
    expense: null,
    income: null,
    investment: null,
    investmentDelta: null,
  };

  const parseJson = (id) => {
    const script = document.getElementById(id);
    if (!script) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (error) {
      console.error("Erro ao ler dados anuais:", error);
      return null;
    }
  };

  const destroyCharts = () => {
    Object.values(charts).forEach((chart) => chart?.destroy());
    charts.expense = null;
    charts.income = null;
    charts.investment = null;
    charts.investmentDelta = null;
  };

  const initCharts = () => {
    const expenseData = parseJson("annual-expense-chart-data");
    const incomeData = parseJson("annual-income-chart-data");
    const investmentData = parseJson("annual-investment-chart-data");
    const investmentDeltaData = parseJson("annual-investment-delta-data");

    const expenseCanvas = document.getElementById("annualExpenseChart");
    const incomeCanvas = document.getElementById("annualIncomeChart");
    const investmentCanvas = document.getElementById("annualInvestmentChart");
    const investmentDeltaCanvas = document.getElementById("annualInvestmentDeltaChart");

    if (!expenseCanvas || !incomeCanvas || !investmentCanvas || !investmentDeltaCanvas) {
      return;
    }

    destroyCharts();

    charts.expense = new Chart(expenseCanvas, {
      type: "doughnut",
      data: {
        labels: expenseData?.labels || [],
        datasets: [
          {
            data: expenseData?.data || [],
            backgroundColor: [
              "#ef4444",
              "#f97316",
              "#facc15",
              "#4ade80",
              "#38bdf8",
              "#a855f7",
            ],
          },
        ],
      },
    });

    charts.income = new Chart(incomeCanvas, {
      type: "doughnut",
      data: {
        labels: incomeData?.labels || [],
        datasets: [
          {
            data: incomeData?.data || [],
            backgroundColor: [
              "#22c55e",
              "#2dd4bf",
              "#60a5fa",
              "#f472b6",
              "#facc15",
              "#a855f7",
            ],
          },
        ],
      },
    });

    charts.investment = new Chart(investmentCanvas, {
      type: "line",
      data: {
        labels: investmentData?.labels || [],
        datasets: [
          {
            label: "Saldo",
            data: investmentData?.data || [],
            borderColor: "#0ea5e9",
            backgroundColor: "rgba(14, 165, 233, 0.2)",
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
      },
    });

    charts.investmentDelta = new Chart(investmentDeltaCanvas, {
      type: "bar",
      data: {
        labels: investmentDeltaData?.labels || [],
        datasets: [
          {
            label: "% mensal",
            data: investmentDeltaData?.data || [],
            backgroundColor: "rgba(16, 185, 129, 0.4)",
            borderColor: "#10b981",
          },
        ],
      },
    });
  };

  document.addEventListener("DOMContentLoaded", initCharts);
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target?.id === "annual-stats-summary") {
      initCharts();
    }
  });
})();
