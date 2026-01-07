export const appState = {
  year: null,
  month: null,
  data: {
    cards: [],
    purchases: [],
    recurring: [],
    totals: { total_month: 0, total_card: 0, total_recurring: 0 },
  },
  filters: {
    purchaseSearch: "",
    purchaseCard: "all",
    purchaseType: "all",
    purchaseSort: "date",
    recurringSearch: "",
    recurringSort: "date",
  },
};

export const elements = {};

export const chartState = {
  line: null,
  doughnut: null,
};

export const monthNames = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

export const logsState = {
  items: [],
};
