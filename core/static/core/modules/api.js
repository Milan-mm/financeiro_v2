import { getCookie, showToast } from "./utils.js";

export const apiFetch = async (url, options = {}) => {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const csrfToken = getCookie("csrftoken");
  if (csrfToken) {
    headers["X-CSRFToken"] = csrfToken;
  }

  let response;
  try {
    response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers,
    });
  } catch (error) {
    showToast("Erro de conexão. Tente novamente.", "danger");
    throw error;
  }

  if (!response.ok) {
    const textData = await response.text();
    let errorDetail = "";

    try {
      const data = JSON.parse(textData);
      errorDetail = data.error || data.detail || JSON.stringify(data);
    } catch (error) {
      errorDetail = `Erro ${response.status} no servidor.`;
      console.error("Conteúdo do erro não-JSON:", textData);
    }
    throw new Error(errorDetail);
  }

  return response.json();
};
