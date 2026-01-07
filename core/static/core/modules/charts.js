import { appState, chartState } from "./state.js";

export const renderCharts = () => {
  const lineCanvas = document.getElementById("lineChart");
  const doughnutCanvas = document.getElementById("doughnutChart");
  if (!lineCanvas && !doughnutCanvas) return;
  if (typeof Chart === "undefined") return;

  const purchases = appState.data.purchases || [];

  if (doughnutCanvas) {
    const totalsByCard = new Map();
    purchases.forEach((item) => {
      const key = item.cartao_nome || "Sem cartão";
      const current = totalsByCard.get(key) || 0;
      totalsByCard.set(key, current + Number(item.valor_parcela || 0));
    });
    const cardLabels = appState.data.cards.length
      ? appState.data.cards.map((card) => card.nome)
      : Array.from(totalsByCard.keys());
    const dataValues = cardLabels.map((label) => totalsByCard.get(label) || 0);
    const colors = [
      "#4c7dff",
      "#22c55e",
      "#f97316",
      "#06b6d4",
      "#a855f7",
      "#f43f5e",
      "#64748b",
    ];
    chartState.doughnut?.destroy();
    chartState.doughnut = new Chart(doughnutCanvas, {
      type: "doughnut",
      data: {
        labels: cardLabels,
        datasets: [
          {
            data: dataValues,
            backgroundColor: cardLabels.map((_, index) => colors[index % colors.length]),
          },
        ],
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
  }

  if (lineCanvas) {
    const daysInMonth = new Date(appState.year, appState.month, 0).getDate();
    const dailyTotals = Array(daysInMonth).fill(0);
    purchases.forEach((item) => {
      const dueDate = new Date(item.vencimento);
      const dayIndex = dueDate.getDate() - 1;
      if (dayIndex >= 0 && dayIndex < dailyTotals.length) {
        dailyTotals[dayIndex] += Number(item.valor_parcela || 0);
      }
    });
    const cumulativeTotals = [];
    dailyTotals.reduce((acc, value) => {
      const nextValue = acc + value;
      cumulativeTotals.push(nextValue);
      return nextValue;
    }, 0);

    chartState.line?.destroy();
    chartState.line = new Chart(lineCanvas, {
      type: "line",
      data: {
        labels: Array.from({ length: daysInMonth }, (_, index) => `${index + 1}`),
        datasets: [
          {
            label: "Gasto acumulado",
            data: cumulativeTotals,
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
          legend: {
            display: false,
          },
        },
        scales: {
          x: {
            grid: {
              display: false,
            },
          },
        },
      },
    });
  }
};
