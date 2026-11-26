/**
 * history.js — Daftar riwayat pengeluaran, pencarian nama barang, filter bulan/tahun/kategori,
 * edit item (PUT /api/items/{id}), serta hapus item/transaksi dengan dialog konfirmasi.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("history-search-input");
    const categorySelect = document.getElementById("history-category-select");
    const monthSelect = document.getElementById("history-month-select");
    const yearSelect = document.getElementById("history-year-select");
    const resetFilterBtn = document.getElementById("btn-reset-history-filter");

    const historyAlert = document.getElementById("history-alert");
    const countLabel = document.getElementById("history-count-label");
    const loadingEl = document.getElementById("history-loading");
    const emptyStateEl = document.getElementById("history-empty-state");
    const emptyTitleEl = document.getElementById("history-empty-title");
    const emptyDescEl = document.getElementById("history-empty-desc");
    const tableWrapper = document.getElementById("history-table-wrapper");
    const tbody = document.getElementById("history-tbody");

    // Edit Modal Elements
    const editBackdrop = document.getElementById("edit-modal-backdrop");
    const editForm = document.getElementById("edit-item-form");
    const editAlert = document.getElementById("edit-modal-alert");
    const editIdInput = document.getElementById("edit-item-id");
    const editDateInput = document.getElementById("edit-item-date");
    const editNameInput = document.getElementById("edit-item-name");
    const editCategorySelect = document.getElementById("edit-item-category");
    const editPriceInput = document.getElementById("edit-item-price");
    const closeEditBtn = document.getElementById("btn-close-edit-modal");
    const cancelEditBtn = document.getElementById("btn-cancel-edit-modal");
    const submitEditBtn = document.getElementById("btn-submit-edit-modal");

    // Delete Confirmation Modal Elements
    const deleteBackdrop = document.getElementById("delete-modal-backdrop");
    const deleteMessageEl = document.getElementById("delete-modal-message");
    const closeDeleteBtn = document.getElementById("btn-close-delete-modal");
    const cancelDeleteBtn = document.getElementById("btn-cancel-delete-modal");
    const confirmDeleteBtn = document.getElementById("btn-confirm-delete-modal");

    let searchDebounceTimer = null;
    let isSubmittingEdit = false;
    let isSubmittingDelete = false;
    let pendingDeleteAction = null;
    const knownYears = new Set();

    ExTraUI.populateCategorySelect(categorySelect, "", true);
    ExTraUI.populateCategorySelect(editCategorySelect, ExTraUI.DEFAULT_CATEGORY, false);

    function populateYearOptions() {
      const currentSelected = yearSelect.value;
      const nowYear = new Date().getFullYear();
      for (let y = nowYear + 1; y >= 2020; y -= 1) {
        knownYears.add(y);
      }

      const sortedYears = Array.from(knownYears)
        .filter((y) => Number.isInteger(y) && y >= 1000 && y <= 9999)
        .sort((a, b) => b - a);

      yearSelect.replaceChildren();
      const allOpt = document.createElement("option");
      allOpt.value = "";
      allOpt.textContent = "Semua Tahun";
      yearSelect.appendChild(allOpt);

      sortedYears.forEach((yr) => {
        const opt = document.createElement("option");
        opt.value = String(yr);
        opt.textContent = String(yr);
        yearSelect.appendChild(opt);
      });

      if (currentSelected && sortedYears.includes(Number(currentSelected))) {
        yearSelect.value = currentSelected;
      }
    }

    function hasActiveFilters() {
      return Boolean(
        (searchInput.value || "").trim() ||
          categorySelect.value !== "" ||
          monthSelect.value !== "" ||
          yearSelect.value !== ""
      );
    }

    function openEditModal(item) {
      ExTraUI.hideAlert(editAlert);
      editIdInput.value = String(item.id);
      editDateInput.value = item.date;
      editNameInput.value = item.name;
      editCategorySelect.value = ExTraUI.normalizeCategory(item.category);
      editPriceInput.value = String(item.price);

      editDateInput.classList.remove("input-invalid");
      editNameInput.classList.remove("input-invalid");
      editCategorySelect.classList.remove("input-invalid");
      editPriceInput.classList.remove("input-invalid");

      editBackdrop.hidden = false;
      editNameInput.focus();
    }

    function closeEditModal() {
      if (isSubmittingEdit) return;
      editBackdrop.hidden = true;
    }

    function openDeleteModal({ mode, item }) {
      pendingDeleteAction = { mode, item };
      if (mode === "transaction") {
        deleteMessageEl.textContent =
          `Hapus seluruh transaksi tanggal ${ExTraUI.formatDateHuman(item.date)} ` +
          `(ID Transaksi #${item.transaction_id}) beserta semua barang di dalamnya?`;
      } else {
        deleteMessageEl.textContent =
          `Apakah Anda yakin ingin menghapus "${item.name}" ` +
          `(${ExTraUI.formatRupiah(item.price)}) pada tanggal ${ExTraUI.formatDateHuman(item.date)}?`;
      }
      deleteBackdrop.hidden = false;
      confirmDeleteBtn.focus();
    }

    function closeDeleteModal() {
      if (isSubmittingDelete) return;
      pendingDeleteAction = null;
      deleteBackdrop.hidden = true;
    }

    function renderHistoryRows(items) {
      tbody.replaceChildren();

      items.forEach((item) => {
        if (typeof item.date === "string" && /^\d{4}-/.test(item.date)) {
          const yr = Number(item.date.slice(0, 4));
          if (!knownYears.has(yr)) {
            knownYears.add(yr);
            populateYearOptions();
          }
        }

        const tr = document.createElement("tr");

        const tdDate = document.createElement("td");
        const dateMain = document.createElement("span");
        dateMain.textContent = ExTraUI.formatDateHuman(item.date);
        const dateSub = document.createElement("span");
        dateSub.className = "date-cell-sub";
        dateSub.textContent = item.date;
        tdDate.append(dateMain, dateSub);

        const tdName = document.createElement("td");
        tdName.textContent = item.name;

        const tdCategory = document.createElement("td");
        const catBadge = document.createElement("span");
        catBadge.className = "badge badge-category";
        catBadge.textContent = ExTraUI.normalizeCategory(item.category);
        tdCategory.appendChild(catBadge);

        const tdPrice = document.createElement("td");
        tdPrice.className = "text-right";
        const priceStrong = document.createElement("strong");
        priceStrong.textContent = ExTraUI.formatRupiah(item.price);
        tdPrice.appendChild(priceStrong);

        const tdActions = document.createElement("td");
        tdActions.className = "col-actions";
        const actionsWrap = document.createElement("div");
        actionsWrap.className = "row-actions";

        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.className = "btn btn-sm btn-secondary";
        editBtn.textContent = "Edit";
        editBtn.addEventListener("click", () => openEditModal(item));

        const delItemBtn = document.createElement("button");
        delItemBtn.type = "button";
        delItemBtn.className = "btn btn-sm btn-ghost-danger";
        delItemBtn.textContent = "Hapus";
        delItemBtn.addEventListener("click", () =>
          openDeleteModal({ mode: "item", item })
        );

        const delTxBtn = document.createElement("button");
        delTxBtn.type = "button";
        delTxBtn.className = "btn btn-sm btn-ghost-danger";
        delTxBtn.title = "Hapus seluruh item dalam struk/transaksi ini";
        delTxBtn.textContent = "Hapus Struk";
        delTxBtn.addEventListener("click", () =>
          openDeleteModal({ mode: "transaction", item })
        );

        actionsWrap.append(editBtn, delItemBtn, delTxBtn);
        tdActions.appendChild(actionsWrap);

        tr.append(tdDate, tdName, tdCategory, tdPrice, tdActions);
        tbody.appendChild(tr);
      });
    }

    async function loadHistory() {
      ExTraUI.hideAlert(historyAlert);
      loadingEl.hidden = false;
      emptyStateEl.hidden = true;
      tableWrapper.hidden = true;

      const filters = {
        month: monthSelect.value || undefined,
        year: yearSelect.value || undefined,
        category: categorySelect.value || undefined,
        search: (searchInput.value || "").trim() || undefined,
      };

      try {
        const response = await ExTraApi.getTransactions(filters);
        const items = Array.isArray(response.data) ? response.data : [];
        const count = typeof response.count === "number" ? response.count : items.length;

        countLabel.textContent = `Menampilkan ${count} item tercatat`;

        if (items.length === 0) {
          if (hasActiveFilters()) {
            emptyTitleEl.textContent = "Tidak ada barang yang cocok";
            emptyDescEl.textContent =
              "Coba ubah kata kunci pencarian, kategori, atau pilih periode bulan dan tahun lainnya.";
          } else {
            emptyTitleEl.textContent = "Belum ada catatan transaksi";
            emptyDescEl.textContent =
              "Unggah foto struk belanja atau catat manual melalui tab Catat Pengeluaran.";
          }
          emptyStateEl.hidden = false;
        } else {
          renderHistoryRows(items);
          tableWrapper.hidden = false;
        }
      } catch (err) {
        countLabel.textContent = "Gagal memuat riwayat";
        ExTraUI.showAlert(
          historyAlert,
          err.message || "Gagal mengambil daftar riwayat transaksi.",
          "error"
        );
      } finally {
        loadingEl.hidden = true;
      }
    }

    // Filter & Search Event Listeners
    searchInput.addEventListener("input", () => {
      if (searchDebounceTimer) {
        clearTimeout(searchDebounceTimer);
      }
      searchDebounceTimer = setTimeout(() => {
        loadHistory();
      }, 260);
    });

    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        if (searchDebounceTimer) {
          clearTimeout(searchDebounceTimer);
        }
        loadHistory();
      }
    });

    categorySelect.addEventListener("change", loadHistory);
    monthSelect.addEventListener("change", loadHistory);
    yearSelect.addEventListener("change", loadHistory);

    resetFilterBtn.addEventListener("click", () => {
      searchInput.value = "";
      categorySelect.value = "";
      monthSelect.value = "";
      yearSelect.value = "";
      loadHistory();
    });

    // Edit Modal Listeners
    closeEditBtn.addEventListener("click", closeEditModal);
    cancelEditBtn.addEventListener("click", closeEditModal);
    editBackdrop.addEventListener("click", (event) => {
      if (event.target === editBackdrop) {
        closeEditModal();
      }
    });

    editForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (isSubmittingEdit) return;
      ExTraUI.hideAlert(editAlert);

      const itemId = Number(editIdInput.value);
      const newDate = (editDateInput.value || "").trim();
      const newName = (editNameInput.value || "").trim();
      const newCategory = (editCategorySelect.value || "").trim();
      const newPrice = ExTraUI.parseStrictNonNegativeInt(editPriceInput.value);

      if (!ExTraUI.isValidIsoCalendarDate(newDate)) {
        editDateInput.classList.add("input-invalid");
        ExTraUI.showAlert(editAlert, "Tanggal transaksi tidak valid.", "error");
        return;
      }
      editDateInput.classList.remove("input-invalid");

      if (!newName) {
        editNameInput.classList.add("input-invalid");
        ExTraUI.showAlert(editAlert, "Nama barang tidak boleh kosong.", "error");
        return;
      }
      editNameInput.classList.remove("input-invalid");

      if (!ExTraUI.isValidCategory(newCategory)) {
        editCategorySelect.classList.add("input-invalid");
        ExTraUI.showAlert(editAlert, "Kategori pengeluaran tidak valid.", "error");
        return;
      }
      editCategorySelect.classList.remove("input-invalid");

      if (newPrice === null) {
        editPriceInput.classList.add("input-invalid");
        ExTraUI.showAlert(
          editAlert,
          "Harga barang harus berupa bilangan bulat minimal 0.",
          "error"
        );
        return;
      }
      editPriceInput.classList.remove("input-invalid");

      isSubmittingEdit = true;
      submitEditBtn.disabled = true;
      cancelEditBtn.disabled = true;
      submitEditBtn.textContent = "Menyimpan...";

      try {
        await ExTraApi.updateItem(itemId, {
          name: newName,
          category: newCategory,
          price: newPrice,
          date: newDate,
        });
        isSubmittingEdit = false;
        closeEditModal();
        ExTraUI.showToast("Perubahan item berhasil disimpan.");
        ExTraUI.notifyDataChanged({ date: newDate });
      } catch (err) {
        ExTraUI.showAlert(
          editAlert,
          err.message || "Gagal memperbarui item.",
          "error"
        );
      } finally {
        isSubmittingEdit = false;
        submitEditBtn.disabled = false;
        cancelEditBtn.disabled = false;
        submitEditBtn.textContent = "Simpan Perubahan";
      }
    });

    // Delete Modal Listeners
    closeDeleteBtn.addEventListener("click", closeDeleteModal);
    cancelDeleteBtn.addEventListener("click", closeDeleteModal);
    deleteBackdrop.addEventListener("click", (event) => {
      if (event.target === deleteBackdrop) {
        closeDeleteModal();
      }
    });

    confirmDeleteBtn.addEventListener("click", async () => {
      if (isSubmittingDelete || !pendingDeleteAction) return;

      const { mode, item } = pendingDeleteAction;
      isSubmittingDelete = true;
      confirmDeleteBtn.disabled = true;
      cancelDeleteBtn.disabled = true;
      confirmDeleteBtn.textContent = "Menghapus...";

      try {
        if (mode === "transaction") {
          await ExTraApi.deleteTransaction(item.transaction_id);
          ExTraUI.showToast("Transaksi beserta seluruh item berhasil dihapus.");
        } else {
          await ExTraApi.deleteItem(item.id);
          ExTraUI.showToast(`Item "${item.name}" berhasil dihapus.`);
        }
        isSubmittingDelete = false;
        closeDeleteModal();
        ExTraUI.notifyDataChanged({ date: item.date });
      } catch (err) {
        isSubmittingDelete = false;
        closeDeleteModal();
        ExTraUI.showAlert(
          historyAlert,
          err.message || "Gagal menghapus data.",
          "error"
        );
      } finally {
        isSubmittingDelete = false;
        confirmDeleteBtn.disabled = false;
        cancelDeleteBtn.disabled = false;
        confirmDeleteBtn.textContent = "Ya, Hapus";
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (!editBackdrop.hidden) closeEditModal();
        if (!deleteBackdrop.hidden) closeDeleteModal();
      }
    });

    // Sinkronisasi otomatis lintas tab
    document.addEventListener("extra:data-changed", () => {
      loadHistory();
    });

    document.addEventListener("extra:tab-activated", (event) => {
      if (event.detail && event.detail.tab === "history") {
        loadHistory();
      }
    });

    populateYearOptions();
    loadHistory();
  });
})();
