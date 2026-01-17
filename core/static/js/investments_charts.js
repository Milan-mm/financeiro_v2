(() => {
  const charts = {
    total: null,
    delta: null,
    accounts: null,
  };

  const parseJson = (id) => {
    const script = document.getElementById(id);
    if (!script) return null;
    try {
      return JSON.parse(script.textContent);
    } catch (error) {
      console.error("Erro ao ler dados de investimentos:", error);
      return null;
    }
  };

  const destroyCharts = () => {
    Object.values(charts).forEach((chart) => chart?.destroy());
    charts.total = null;
    charts.delta = null;
    charts.accounts = null;
  };

  const initCharts = () => {
    const totalData = parseJson("investments-total-data");
    const deltaData = parseJson("investments-delta-data");
    const accountData = parseJson("investments-account-data");
    const totalCanvas = document.getElementById("investmentsTotalChart");
    const deltaCanvas = document.getElementById("investmentsDeltaChart");
    const accountCanvas = document.getElementById("investmentsAccountChart");

    if (!totalCanvas || !deltaCanvas || !accountCanvas || !totalData || !deltaData || !accountData) {
      return;
    }

    destroyCharts();

    charts.total = new Chart(totalCanvas, {
      type: "line",
      data: {
        labels: totalData.labels,
        datasets: [
          {
            label: "Saldo total",
            data: totalData.data,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.2)",
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            ticks: {
              callback: (value) => `R$ ${value}`,
            },
          },
        },
      },
    });

    charts.delta = new Chart(deltaCanvas, {
      type: "bar",
      data: {
        labels: deltaData.labels,
        datasets: [
          {
            label: "% mensal",
            data: deltaData.data,
            backgroundColor: "rgba(14, 116, 144, 0.4)",
            borderColor: "#0e7490",
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            ticks: {
              callback: (value) => `${value}%`,
            },
          },
        },
      },
    });

    charts.accounts = new Chart(accountCanvas, {
      type: "line",
      data: {
        labels: accountData.labels,
        datasets: accountData.datasets.map((dataset) => ({
          label: dataset.label,
          data: dataset.data,
          tension: 0.3,
        })),
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });

    const toggle = document.getElementById("toggleAccountTrends");
    if (toggle) {
      const toggleDatasets = () => {
        const hidden = !toggle.checked;
        charts.accounts.data.datasets.forEach((dataset) => {
          dataset.hidden = hidden;
        });
        charts.accounts.update();
      };
      toggle.removeEventListener("change", toggleDatasets);
      toggle.addEventListener("change", toggleDatasets);
      toggleDatasets();
    }
  };

  document.addEventListener("DOMContentLoaded", initCharts);
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target?.id === "investments-summary") {
      initCharts();
    }
  });
})();
