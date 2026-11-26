/**
 * api.js — Wrapper fetch REST API terpusat, utilitas format, & kontrol tab ExTra.
 * Seluruh komunikasi ke backend melewati modul ini (tanpa akses langsung ke Gemini API).
 */
(function () {
  "use strict";

  const MONTH_NAMES_ID = [
    "",
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
  ];

  const MONTH_SHORT_ID = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
  ];

  const EXPENSE_CATEGORIES = Object.freeze([
    "Makanan & Minuman",
    "Kebutuhan Pokok",
    "Transportasi",
    "Kesehatan & Perawatan",
    "Tagihan & Utilitas",
    "Hiburan & Belanja",
    "Lainnya",
  ]);
  const DEFAULT_CATEGORY = "Lainnya";

  const idrNumberFormatter = new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 0,
  });

  class ApiError extends Error {
    constructor(message, status, errorCode, details) {
      super(message);
      this.name = "ApiError";
      this.status = status || 0;
      this.errorCode = errorCode || "UNKNOWN_ERROR";
      this.details = Array.isArray(details) ? details : [];
    }
  }

  async function requestApi(url, options = {}) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (_networkErr) {
      throw new ApiError(
        "Tidak dapat terhubung ke server ExTra. Pastikan backend sedang berjalan.",
        0,
        "NETWORK_ERROR",
        []
      );
    }

    let payload = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        payload = await response.json();
      } catch (_parseErr) {
        payload = null;
      }
    }

    if (!response.ok || (payload && payload.status === "error")) {
      const message =
        (payload && typeof payload.message === "string" && payload.message.trim()) ||
        `Permintaan gagal diproses (HTTP ${response.status}).`;
      const errorCode =
        (payload && payload.error_code) || `HTTP_${response.status}`;
      const details = (payload && payload.details) || [];
      throw new ApiError(message, response.status, errorCode, details);
    }

    if (!payload) {
      throw new ApiError(
        "Respons server tidak berformat JSON yang valid.",
        response.status,
        "INVALID_SERVER_RESPONSE",
        []
      );
    }

    return payload;
  }

  /**
   * Wrapper endpoint REST API ExTra sesuai Section 13 PRD.md.
   */
  const ExTraApi = {
    ApiError,

    async extractReceipt(file) {
      const formData = new FormData();
      formData.append("file", file);
      return requestApi("/api/receipts/extract", {
        method: "POST",
        body: formData,
      });
    },

    async createTransaction(payload) {
      return requestApi("/api/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },

    async getTransactions({ month, year, category, search } = {}) {
      const params = new URLSearchParams();
      if (month !== undefined && month !== null && String(month) !== "") {
        params.set("month", String(month));
      }
      if (year !== undefined && year !== null && String(year) !== "") {
        params.set("year", String(year));
      }
      if (category !== undefined && category !== null && String(category).trim() !== "") {
        params.set("category", String(category).trim());
      }
      if (search !== undefined && search !== null && String(search).trim() !== "") {
        params.set("search", String(search).trim());
      }
      const queryString = params.toString();
      const url = queryString ? `/api/transactions?${queryString}` : "/api/transactions";
      return requestApi(url, { method: "GET" });
    },

    async updateItem(itemId, payload) {
      return requestApi(`/api/items/${encodeURIComponent(itemId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },

    async deleteItem(itemId) {
      return requestApi(`/api/items/${encodeURIComponent(itemId)}`, {
        method: "DELETE",
      });
    },

    async deleteTransaction(transactionId) {
      return requestApi(`/api/transactions/${encodeURIComponent(transactionId)}`, {
        method: "DELETE",
      });
    },

    async getMonthlySummary(month, year) {
      const params = new URLSearchParams({
        month: String(month),
        year: String(year),
      });
      return requestApi(`/api/summary/monthly?${params.toString()}`, {
        method: "GET",
      });
    },
  };

  /**
   * Utilitas tampilan & navigasi UI lintas modul.
   */
  let toastTimer = null;

  function formatRupiah(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "Rp 0";
    }
    return `Rp ${idrNumberFormatter.format(Math.trunc(numeric))}`;
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) {
      return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  function formatDateHuman(isoDate) {
    if (typeof isoDate !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
      return isoDate || "-";
    }
    const [yearStr, monthStr, dayStr] = isoDate.split("-");
    const monthIdx = Number(monthStr);
    const dayNum = Number(dayStr);
    return `${dayNum} ${MONTH_SHORT_ID[monthIdx] || monthStr} ${yearStr}`;
  }

  function getMonthName(monthNumber) {
    return MONTH_NAMES_ID[Number(monthNumber)] || "";
  }

  function isValidIsoCalendarDate(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      return false;
    }
    const [y, m, d] = value.split("-").map(Number);
    const candidate = new Date(Date.UTC(y, m - 1, d));
    return (
      candidate.getUTCFullYear() === y &&
      candidate.getUTCMonth() === m - 1 &&
      candidate.getUTCDate() === d
    );
  }

  function parseStrictNonNegativeInt(rawValue) {
    const trimmed = String(rawValue ?? "").trim();
    if (!/^\d+$/.test(trimmed)) {
      return null;
    }
    const parsed = Number(trimmed);
    if (!Number.isSafeInteger(parsed) || parsed < 0) {
      return null;
    }
    return parsed;
  }

  function normalizeCategory(rawCategory) {
    const trimmed = String(rawCategory ?? "").trim();
    return EXPENSE_CATEGORIES.includes(trimmed) ? trimmed : DEFAULT_CATEGORY;
  }

  function isValidCategory(rawCategory) {
    const trimmed = String(rawCategory ?? "").trim();
    return EXPENSE_CATEGORIES.includes(trimmed);
  }

  function populateCategorySelect(selectEl, selectedValue = DEFAULT_CATEGORY, includeAllOption = false) {
    if (!selectEl) return;
    selectEl.replaceChildren();

    if (includeAllOption) {
      const allOpt = document.createElement("option");
      allOpt.value = "";
      allOpt.textContent = "Semua Kategori";
      selectEl.appendChild(allOpt);
    }

    EXPENSE_CATEGORIES.forEach((cat) => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      selectEl.appendChild(opt);
    });

    if (includeAllOption && (!selectedValue || !EXPENSE_CATEGORIES.includes(selectedValue))) {
      selectEl.value = "";
    } else {
      selectEl.value = normalizeCategory(selectedValue);
    }
  }

  function getTodayIsoDate() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function showAlert(element, message, variant = "error") {
    if (!element) return;
    element.className = `alert alert-${variant}`;
    element.textContent = message;
    element.hidden = false;
  }

  function hideAlert(element) {
    if (!element) return;
    element.textContent = "";
    element.hidden = true;
  }

  function showToast(message, actionLabel, onAction) {
    const toastEl = document.getElementById("global-toast");
    if (!toastEl) return;

    if (toastTimer) {
      clearTimeout(toastTimer);
      toastTimer = null;
    }

    toastEl.replaceChildren();
    const textSpan = document.createElement("span");
    textSpan.textContent = message;
    toastEl.appendChild(textSpan);

    if (actionLabel && typeof onAction === "function") {
      const actionBtn = document.createElement("button");
      actionBtn.type = "button";
      actionBtn.className = "btn btn-sm btn-secondary";
      actionBtn.textContent = actionLabel;
      actionBtn.addEventListener("click", () => {
        toastEl.hidden = true;
        onAction();
      });
      toastEl.appendChild(actionBtn);
    }

    toastEl.hidden = false;
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 5500);
  }

  function switchTab(targetTab) {
    const tabButtons = document.querySelectorAll(".nav-tab[data-tab]");
    const panels = {
      upload: document.getElementById("panel-upload"),
      history: document.getElementById("panel-history"),
      summary: document.getElementById("panel-summary"),
    };

    if (!panels[targetTab]) return;

    tabButtons.forEach((btn) => {
      const isActive = btn.dataset.tab === targetTab;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    Object.entries(panels).forEach(([key, panelEl]) => {
      if (!panelEl) return;
      const isMatch = key === targetTab;
      panelEl.classList.toggle("active", isMatch);
      panelEl.hidden = !isMatch;
    });

    document.dispatchEvent(
      new CustomEvent("extra:tab-activated", { detail: { tab: targetTab } })
    );
  }

  function notifyDataChanged(detail = {}) {
    document.dispatchEvent(new CustomEvent("extra:data-changed", { detail }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".nav-tab[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        switchTab(btn.dataset.tab);
      });
    });
  });

  window.ExTraApi = ExTraApi;
  window.ExTraUI = {
    EXPENSE_CATEGORIES,
    DEFAULT_CATEGORY,
    formatRupiah,
    formatFileSize,
    formatDateHuman,
    getMonthName,
    isValidIsoCalendarDate,
    parseStrictNonNegativeInt,
    normalizeCategory,
    isValidCategory,
    populateCategorySelect,
    getTodayIsoDate,
    showAlert,
    hideAlert,
    showToast,
    switchTab,
    notifyDataChanged,
  };
})();
