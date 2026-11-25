/**
 * summary.js — Ringkasan pengeluaran bulanan & grafik batang SVG murni.
 * Seluruh metrik diambil langsung dari GET /api/summary/monthly tanpa kalkulasi ulang di klien.
 */
(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  function createSvgElement(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, val]) => {
      el.setAttribute(key, String(val));
    });
    return el;
  }

  function formatCompactIdr(value) {
    const num = Number(value) || 0;
    if (num >= 1_000_000) {
      const jt = num / 1_000_000;
      const formatted = Number.isInteger(jt) ? String(jt) : jt.toFixed(1).replace(".", ",");
      return `Rp ${formatted}jt`;
    }
    if (num >= 1_000) {
      const rb = Math.round(num / 1_000);
      return `Rp ${rb}rb`;
    }
    return `Rp ${num}`;
  }

  function computeNiceMax(maxVal) {
    if (maxVal <= 0) return 10_000;
    const magnitude = Math.pow(10, Math.floor(Math.log10(maxVal)));
    const normalized = maxVal / magnitude;
    let niceNormalized = 10;
    if (normalized <= 1) niceNormalized = 1;
    else if (normalized <= 2) niceNormalized = 2;
    else if (normalized <= 5) niceNormalized = 5;
    return niceNormalized * magnitude;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const monthSelect = document.getElementById("summary-month-select");
    const yearSelect = document.getElementById("summary-year-select");
    const summaryAlert = document.getElementById("summary-alert");

    const totalExpenseEl = document.getElementById("summary-total-expense");
    const totalItemsEl = document.getElementById("summary-total-items");
    const periodCaptionEl = document.getElementById("summary-period-caption");

    const loadingEl = document.getElementById("summary-loading");
    const emptyStateEl = document.getElementById("summary-empty-state");
    const summaryContentEl = document.getElementById("summary-content");
    const chartContainer = document.getElementById("summary-chart-container");
    const dailyTbody = document.getElementById("summary-daily-tbody");

    function initPeriodSelectors() {
      const now = new Date();
      const currentMonth = now.getMonth() + 1;
      const currentYear = Math.min(2100, Math.max(2000, now.getFullYear()));

      const maxYear = Math.min(2100, currentYear + 2);
      const minYear = 2020;

      yearSelect.replaceChildren();
      for (let y = maxYear; y >= minYear; y -= 1) {
        const opt = document.createElement("option");
        opt.value = String(y);
        opt.textContent = String(y);
        yearSelect.appendChild(opt);
      }

      monthSelect.value = String(currentMonth);
      yearSelect.value = String(currentYear);
    }

    function ensureYearOptionExists(yearNum) {
      if (!Number.isInteger(yearNum) || yearNum < 2000 || yearNum > 2100) return;
      const exists = Array.from(yearSelect.options).some(
        (opt) => Number(opt.value) === yearNum
      );
      if (!exists) {
        const opt = document.createElement("option");
        opt.value = String(yearNum);
        opt.textContent = String(yearNum);
        yearSelect.appendChild(opt);
      }
    }

    function renderBarChart(dailyBreakdown) {
      chartContainer.replaceChildren();
      if (!Array.isArray(dailyBreakdown) || dailyBreakdown.length === 0) {
        return;
      }

      const barStep = 58;
      const paddingLeft = 74;
      const paddingRight = 24;
      const paddingTop = 28;
      const paddingBottom = 46;
      const plotHeight = 210;

      const svgWidth = Math.max(
        560,
        paddingLeft + paddingRight + dailyBreakdown.length * barStep
      );
      const svgHeight = paddingTop + plotHeight + paddingBottom;
      const plotWidth = svgWidth - paddingLeft - paddingRight;

      const rawMax = Math.max(...dailyBreakdown.map((d) => Number(d.total) || 0));
      const yMax = computeNiceMax(rawMax);

      const svg = createSvgElement("svg", {
        class: "summary-svg-chart",
        viewBox: `0 0 ${svgWidth} ${svgHeight}`,
        role: "img",
        "aria-label": "Grafik batang pengeluaran per tanggal",
      });

      // Garis grid horizontal + label sumbu Y
      const ticks = 4;
      for (let i = 0; i <= ticks; i += 1) {
        const ratio = i / ticks;
        const yPos = paddingTop + plotHeight - ratio * plotHeight;
        const tickValue = Math.round(ratio * yMax);

        const line = createSvgElement("line", {
          x1: paddingLeft,
          y1: yPos,
          x2: svgWidth - paddingRight,
          y2: yPos,
          stroke: i === 0 ? "#cbd5e1" : "#e2e8f0",
          "stroke-dasharray": i === 0 ? "none" : "4 4",
          "stroke-width": "1",
        });
        svg.appendChild(line);

        const yLabel = createSvgElement("text", {
          x: paddingLeft - 10,
          y: yPos + 4,
          "text-anchor": "end",
          fill: "#64748b",
          "font-size": "11.5",
        });
        yLabel.textContent = formatCompactIdr(tickValue);
        svg.appendChild(yLabel);
      }

      const slotWidth = plotWidth / dailyBreakdown.length;
      const barWidth = Math.min(36, Math.max(16, slotWidth * 0.58));

      dailyBreakdown.forEach((entry, idx) => {
        const total = Number(entry.total) || 0;
        const barHeight = yMax > 0 ? Math.max(total > 0 ? 3 : 0, (total / yMax) * plotHeight) : 0;
        const centerX = paddingLeft + idx * slotWidth + slotWidth / 2;
        const barX = centerX - barWidth / 2;
        const barY = paddingTop + plotHeight - barHeight;

        const group = createSvgElement("g");

        const rect = createSvgElement("rect", {
          x: barX.toFixed(1),
          y: barY.toFixed(1),
          width: barWidth.toFixed(1),
          height: barHeight.toFixed(1),
          rx: "5",
          fill: "#0f766e",
        });

        const tooltip = createSvgElement("title");
        tooltip.textContent =
          `${ExTraUI.formatDateHuman(entry.date)}: ${ExTraUI.formatRupiah(total)} ` +
          `(${entry.item_count} barang)`;
        rect.appendChild(tooltip);
        group.appendChild(rect);

        // Label nominal di atas batang
        const valText = createSvgElement("text", {
          x: centerX.toFixed(1),
          y: Math.max(14, barY - 6).toFixed(1),
          "text-anchor": "middle",
          fill: "#0f172a",
          "font-size": "11",
          "font-weight": "600",
        });
        valText.textContent = formatCompactIdr(total);
        group.appendChild(valText);

        // Label tanggal DD/MM di sumbu X
        const shortDate =
          typeof entry.date === "string" && entry.date.length === 10
            ? `${entry.date.slice(8, 10)}/${entry.date.slice(5, 7)}`
            : entry.date;

        const dateLabel = createSvgElement("text", {
          x: centerX.toFixed(1),
          y: paddingTop + plotHeight + 22,
          "text-anchor": "middle",
          fill: "#475569",
          "font-size": "11.5",
          "font-weight": "500",
        });
        dateLabel.textContent = shortDate;
        group.appendChild(dateLabel);

        svg.appendChild(group);
      });

      chartContainer.appendChild(svg);
    }

    function renderDailyTable(dailyBreakdown) {
      dailyTbody.replaceChildren();
      dailyBreakdown.forEach((entry) => {
        const tr = document.createElement("tr");

        const tdDate = document.createElement("td");
        const mainSpan = document.createElement("span");
        mainSpan.textContent = ExTraUI.formatDateHuman(entry.date);
        const subSpan = document.createElement("span");
        subSpan.className = "date-cell-sub";
        subSpan.textContent = entry.date;
        tdDate.append(mainSpan, subSpan);

        const tdCount = document.createElement("td");
        tdCount.className = "text-right";
        tdCount.textContent = `${entry.item_count} barang`;

        const tdTotal = document.createElement("td");
        tdTotal.className = "text-right";
        const strongTotal = document.createElement("strong");
        strongTotal.textContent = ExTraUI.formatRupiah(entry.total);
        tdTotal.appendChild(strongTotal);

        tr.append(tdDate, tdCount, tdTotal);
        dailyTbody.appendChild(tr);
      });
    }

    async function loadSummary() {
      ExTraUI.hideAlert(summaryAlert);
      const month = Number(monthSelect.value);
      const year = Number(yearSelect.value);
      const periodLabel = `${ExTraUI.getMonthName(month)} ${year}`;

      loadingEl.hidden = false;
      emptyStateEl.hidden = true;
      summaryContentEl.hidden = true;

      try {
        const summary = await ExTraApi.getMonthlySummary(month, year);

        // Gunakan angka 100% langsung dari backend tanpa kalkulasi ulang di frontend
        totalExpenseEl.textContent = ExTraUI.formatRupiah(summary.total_expense);
        totalItemsEl.textContent = `${summary.total_items} barang`;
        periodCaptionEl.textContent = `Periode ${periodLabel}`;

        const breakdown = Array.isArray(summary.daily_breakdown)
          ? summary.daily_breakdown
          : [];

        if (breakdown.length === 0) {
          chartContainer.replaceChildren();
          dailyTbody.replaceChildren();
          emptyStateEl.hidden = false;
        } else {
          renderBarChart(breakdown);
          renderDailyTable(breakdown);
          summaryContentEl.hidden = false;
        }
      } catch (err) {
        ExTraUI.showAlert(
          summaryAlert,
          err.message || "Gagal memuat ringkasan pengeluaran bulanan.",
          "error"
        );
      } finally {
        loadingEl.hidden = true;
      }
    }

    monthSelect.addEventListener("change", loadSummary);
    yearSelect.addEventListener("change", loadSummary);

    document.addEventListener("extra:data-changed", (event) => {
      const changedDate = event.detail && event.detail.date;
      if (typeof changedDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(changedDate)) {
        ensureYearOptionExists(Number(changedDate.slice(0, 4)));
      }
      loadSummary();
    });

    document.addEventListener("extra:tab-activated", (event) => {
      if (event.detail && event.detail.tab === "summary") {
        loadSummary();
      }
    });

    initPeriodSelectors();
    loadSummary();
  });
})();
