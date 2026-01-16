(() => {
  const updateBadge = async () => {
    const badges = document.querySelectorAll(".logs-pending-badge");
    if (!badges.length) return;
    try {
      const response = await fetch("/api/logs/pending-count/", {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) return;
      const data = await response.json();
      badges.forEach((badge) => {
        if (data.pending > 0) {
          badge.textContent = data.pending;
          badge.classList.remove("d-none");
        } else {
          badge.classList.add("d-none");
        }
      });
    } catch (error) {
      console.error("Erro ao carregar badge de logs:", error);
    }
  };

  document.addEventListener("DOMContentLoaded", updateBadge);
  document.body.addEventListener("logs:refresh", updateBadge);
})();
