/**
 * upload.js — Logika unggah foto struk (AI), tabel preview editable dengan kategori,
 * form Input Manual tanpa struk, serta konfirmasi penyimpanan eksplisit (Human-in-the-Loop).
 */
(function () {
  "use strict";

  const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
  const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"];
  const ALLOWED_MIMES = ["image/jpeg", "image/png"];

  document.addEventListener("DOMContentLoaded", () => {
    // Mode Switch Elements
    const btnModeScan = document.getElementById("btn-mode-scan");
    const btnModeManual = document.getElementById("btn-mode-manual");
    const scanModeContainer = document.getElementById("scan-mode-container");
    const manualModeContainer = document.getElementById("manual-mode-container");

    // Scan & Upload Elements
    const uploadForm = document.getElementById("upload-form");
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("receipt-file-input");
    const dropzonePrompt = document.getElementById("dropzone-prompt");
    const thumbnailContainer = document.getElementById("thumbnail-container");
    const thumbnailImg = document.getElementById("receipt-thumbnail");
    const fileNameEl = document.getElementById("selected-file-name");
    const fileSizeEl = document.getElementById("selected-file-size");

    const btnExtract = document.getElementById("btn-extract");
    const btnClearFile = document.getElementById("btn-clear-file");
    const uploadLoading = document.getElementById("upload-loading");
    const uploadAlert = document.getElementById("upload-alert");

    // Preview Elements
    const previewSection = document.getElementById("preview-section");
    const previewWarningBanner = document.getElementById("preview-warning-banner");
    const previewValidationAlert = document.getElementById("preview-validation-alert");
    const previewDateInput = document.getElementById("preview-date-input");
    const previewDateHelp = document.getElementById("preview-date-help");
    const previewTbody = document.getElementById("preview-items-tbody");
    const previewTotalDisplay = document.getElementById("preview-total-display");
    const previewArchiveCheckbox = document.getElementById("preview-archive-checkbox");

    const btnAddRow = document.getElementById("btn-add-preview-row");
    const btnCancelPreview = document.getElementById("btn-cancel-preview");
    const btnSaveTransaction = document.getElementById("btn-save-transaction");

    // Manual Entry Elements
    const manualForm = document.getElementById("manual-entry-form");
    const manualValidationAlert = document.getElementById("manual-validation-alert");
    const manualDateInput = document.getElementById("manual-date-input");
    const manualTbody = document.getElementById("manual-items-tbody");
    const manualTotalDisplay = document.getElementById("manual-total-display");
    const btnAddManualRow = document.getElementById("btn-add-manual-row");
    const btnResetManual = document.getElementById("btn-reset-manual");
    const btnSaveManual = document.getElementById("btn-save-manual-transaction");

    let selectedFile = null;
    let currentObjectUrl = null;
    let currentTempImageToken = null;
    let isExtracting = false;
    let isSavingPreview = false;
    let isSavingManual = false;

    function switchEntryMode(mode) {
      const isManual = mode === "manual";
      if (isManual) {
        currentTempImageToken = null;
      }
      btnModeScan.classList.toggle("active", !isManual);
      btnModeScan.setAttribute("aria-pressed", isManual ? "false" : "true");
      btnModeManual.classList.toggle("active", isManual);
      btnModeManual.setAttribute("aria-pressed", isManual ? "true" : "false");

      scanModeContainer.hidden = isManual;
      manualModeContainer.hidden = !isManual;
    }

    btnModeScan.addEventListener("click", () => switchEntryMode("scan"));
    btnModeManual.addEventListener("click", () => switchEntryMode("manual"));

    function revokeThumbnailUrl() {
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
        currentObjectUrl = null;
      }
    }

    function validateClientFile(file) {
      if (!file) {
        return "Silakan pilih foto struk terlebih dahulu.";
      }

      const lowerName = (file.name || "").toLowerCase();
      const lowerMime = (file.type || "").toLowerCase();
      const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
      const hasValidMime = lowerMime === "" || ALLOWED_MIMES.includes(lowerMime);

      if (!hasValidExt || !hasValidMime) {
        return "Format file tidak didukung. Pilih gambar berformat JPG, JPEG, atau PNG.";
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        return "Ukuran file melebihi batas maksimal 5 MB. Silakan pilih gambar yang lebih kecil.";
      }

      if (file.size === 0) {
        return "File gambar kosong atau rusak.";
      }

      return null;
    }

    function applySelectedFile(file) {
      ExTraUI.hideAlert(uploadAlert);
      const validationError = validateClientFile(file);
      if (validationError) {
        clearSelectedFile();
        ExTraUI.showAlert(uploadAlert, validationError, "error");
        return;
      }

      revokeThumbnailUrl();
      selectedFile = file;
      currentObjectUrl = URL.createObjectURL(file);

      thumbnailImg.src = currentObjectUrl;
      fileNameEl.textContent = file.name;
      fileSizeEl.textContent = ExTraUI.formatFileSize(file.size);

      dropzonePrompt.hidden = true;
      thumbnailContainer.hidden = false;
      btnExtract.disabled = false;
      btnClearFile.hidden = false;
    }

    function clearSelectedFile() {
      selectedFile = null;
      fileInput.value = "";
      revokeThumbnailUrl();
      thumbnailImg.removeAttribute("src");
      fileNameEl.textContent = "";
      fileSizeEl.textContent = "";
      dropzonePrompt.hidden = false;
      thumbnailContainer.hidden = true;
      btnExtract.disabled = true;
      btnClearFile.hidden = true;
    }

    function refreshTableNumbersAndSubtotal(tbodyEl, totalDisplayEl) {
      const rows = tbodyEl.querySelectorAll("tr.editable-item-row");
      let total = 0;
      rows.forEach((row, index) => {
        const numCell = row.querySelector(".col-num");
        if (numCell) {
          numCell.textContent = String(index + 1);
        }
        const priceInput = row.querySelector(".item-price-input");
        const parsed = ExTraUI.parseStrictNonNegativeInt(priceInput ? priceInput.value : "");
        if (parsed !== null) {
          total += parsed;
        }
      });
      totalDisplayEl.textContent = ExTraUI.formatRupiah(total);
    }

    function createEditableItemRow(
      item = { name: "", price: "", category: ExTraUI.DEFAULT_CATEGORY },
      onChangeCallback = () => {}
    ) {
      const tr = document.createElement("tr");
      tr.className = "editable-item-row preview-item-row";

      const tdNum = document.createElement("td");
      tdNum.className = "col-num";

      const tdName = document.createElement("td");
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.className = "form-control item-name-input preview-name-input";
      nameInput.placeholder = "Nama barang / pengeluaran";
      nameInput.value = item.name != null ? String(item.name) : "";
      nameInput.maxLength = 200;
      nameInput.addEventListener("input", () => {
        nameInput.classList.remove("input-invalid");
      });
      tdName.appendChild(nameInput);

      const tdCategory = document.createElement("td");
      const categorySelect = document.createElement("select");
      categorySelect.className = "form-control item-category-select preview-category-select";
      ExTraUI.populateCategorySelect(
        categorySelect,
        ExTraUI.normalizeCategory(item.category),
        false
      );
      categorySelect.addEventListener("change", () => {
        categorySelect.classList.remove("input-invalid");
      });
      tdCategory.appendChild(categorySelect);

      const tdPrice = document.createElement("td");
      const priceInput = document.createElement("input");
      priceInput.type = "number";
      priceInput.className = "form-control item-price-input preview-price-input";
      priceInput.placeholder = "0";
      priceInput.min = "0";
      priceInput.step = "1";
      priceInput.value =
        item.price !== undefined && item.price !== null && item.price !== ""
          ? String(item.price)
          : "";
      priceInput.addEventListener("input", () => {
        priceInput.classList.remove("input-invalid");
        onChangeCallback();
      });
      tdPrice.appendChild(priceInput);

      const tdAction = document.createElement("td");
      tdAction.className = "col-action-sm";
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "btn btn-sm btn-ghost-danger";
      removeBtn.textContent = "Hapus";
      removeBtn.addEventListener("click", () => {
        tr.remove();
        onChangeCallback();
      });
      tdAction.appendChild(removeBtn);

      tr.append(tdNum, tdName, tdCategory, tdPrice, tdAction);
      return tr;
    }

    function collectAndValidatePayload(dateInputEl, tbodyEl) {
      const dateVal = (dateInputEl.value || "").trim();
      let hasError = false;
      const errorMessages = [];

      if (!ExTraUI.isValidIsoCalendarDate(dateVal)) {
        dateInputEl.classList.add("input-invalid");
        errorMessages.push("Tanggal transaksi wajib diisi dengan tanggal kalender yang valid.");
        hasError = true;
      } else {
        dateInputEl.classList.remove("input-invalid");
      }

      const rowElements = Array.from(tbodyEl.querySelectorAll("tr.editable-item-row"));
      if (rowElements.length === 0) {
        errorMessages.push("Daftar barang minimal harus berisi 1 item.");
        hasError = true;
      }

      const validatedItems = [];
      rowElements.forEach((row, idx) => {
        const nameInput = row.querySelector(".item-name-input");
        const categorySelect = row.querySelector(".item-category-select");
        const priceInput = row.querySelector(".item-price-input");

        const trimmedName = (nameInput.value || "").trim();
        const selectedCategory = (categorySelect.value || "").trim();
        const parsedPrice = ExTraUI.parseStrictNonNegativeInt(priceInput.value);

        if (!trimmedName) {
          nameInput.classList.add("input-invalid");
          errorMessages.push(`Baris #${idx + 1}: Nama barang tidak boleh kosong.`);
          hasError = true;
        } else {
          nameInput.classList.remove("input-invalid");
        }

        if (!ExTraUI.isValidCategory(selectedCategory)) {
          categorySelect.classList.add("input-invalid");
          errorMessages.push(`Baris #${idx + 1}: Pilih kategori pengeluaran yang valid.`);
          hasError = true;
        } else {
          categorySelect.classList.remove("input-invalid");
        }

        if (parsedPrice === null) {
          priceInput.classList.add("input-invalid");
          errorMessages.push(
            `Baris #${idx + 1}: Harga harus berupa bilangan bulat minimal 0.`
          );
          hasError = true;
        } else {
          priceInput.classList.remove("input-invalid");
        }

        if (trimmedName && ExTraUI.isValidCategory(selectedCategory) && parsedPrice !== null) {
          validatedItems.push({
            name: trimmedName,
            price: parsedPrice,
            category: selectedCategory,
          });
        }
      });

      return {
        hasError,
        errorMessage: errorMessages[0] || "",
        date: dateVal,
        items: validatedItems,
      };
    }

    // -------------------------------------------------------------------------
    // Scan Struk & Preview Helpers
    // -------------------------------------------------------------------------
    function refreshPreviewSubtotal() {
      refreshTableNumbersAndSubtotal(previewTbody, previewTotalDisplay);
    }

    function resetPreviewSection() {
      currentTempImageToken = null;
      previewSection.hidden = true;
      previewTbody.replaceChildren();
      previewDateInput.value = "";
      previewDateInput.classList.remove("input-invalid", "input-warning");
      previewDateHelp.textContent = "Format YYYY-MM-DD sesuai tanggal pada struk.";
      previewDateHelp.classList.remove("text-danger");
      if (previewArchiveCheckbox) {
        previewArchiveCheckbox.checked = true;
      }
      ExTraUI.hideAlert(previewWarningBanner);
      ExTraUI.hideAlert(previewValidationAlert);
      previewTotalDisplay.textContent = "Rp 0";
    }

    function setExtractingState(active) {
      isExtracting = active;
      uploadLoading.hidden = !active;
      btnExtract.disabled = active || !selectedFile;
      btnClearFile.disabled = active;
      fileInput.disabled = active;
      dropzone.classList.toggle("disabled", active);
      btnExtract.textContent = active ? "Memproses..." : "Ekstrak Isi Struk";
    }

    function setSavingPreviewState(active) {
      isSavingPreview = active;
      btnSaveTransaction.disabled = active;
      btnCancelPreview.disabled = active;
      btnAddRow.disabled = active;
      btnSaveTransaction.textContent = active
        ? "Menyimpan..."
        : "Konfirmasi & Simpan";
    }

    function openPreviewTable(extractedData, warnings, tempImageToken = null) {
      resetPreviewSection();
      currentTempImageToken = tempImageToken || null;
      if (previewArchiveCheckbox) {
        previewArchiveCheckbox.checked = Boolean(currentTempImageToken);
        previewArchiveCheckbox.disabled = !currentTempImageToken;
      }

      const dateVal = extractedData && extractedData.date ? extractedData.date : "";
      previewDateInput.value = dateVal;

      const warningList = Array.isArray(warnings) ? warnings : [];
      if (!dateVal || warningList.length > 0) {
        const warningText =
          warningList.join(" ") ||
          "Tanggal transaksi tidak terbaca pada struk. Silakan isi manual sebelum menyimpan.";
        ExTraUI.showAlert(previewWarningBanner, warningText, "warning");
        if (!dateVal) {
          previewDateInput.classList.add("input-invalid");
          previewDateHelp.textContent =
            "Tanggal belum terbaca otomatis — wajib diisi manual sebelum menyimpan.";
          previewDateHelp.classList.add("text-danger");
        }
      }

      const items = Array.isArray(extractedData && extractedData.items)
        ? extractedData.items
        : [];

      if (items.length === 0) {
        previewTbody.appendChild(
          createEditableItemRow(
            { name: "", price: "", category: ExTraUI.DEFAULT_CATEGORY },
            refreshPreviewSubtotal
          )
        );
      } else {
        items.forEach((item) => {
          previewTbody.appendChild(
            createEditableItemRow(item, refreshPreviewSubtotal)
          );
        });
      }

      refreshPreviewSubtotal();
      previewSection.hidden = false;
      previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // -------------------------------------------------------------------------
    // Manual Input Helpers
    // -------------------------------------------------------------------------
    function refreshManualSubtotal() {
      refreshTableNumbersAndSubtotal(manualTbody, manualTotalDisplay);
    }

    function resetManualForm() {
      ExTraUI.hideAlert(manualValidationAlert);
      manualDateInput.value = ExTraUI.getTodayIsoDate();
      manualDateInput.classList.remove("input-invalid");
      manualTbody.replaceChildren();
      manualTbody.appendChild(
        createEditableItemRow(
          { name: "", price: "", category: ExTraUI.DEFAULT_CATEGORY },
          refreshManualSubtotal
        )
      );
      refreshManualSubtotal();
    }

    function setSavingManualState(active) {
      isSavingManual = active;
      btnSaveManual.disabled = active;
      btnResetManual.disabled = active;
      btnAddManualRow.disabled = active;
      btnSaveManual.textContent = active
        ? "Menyimpan..."
        : "Konfirmasi & Simpan";
    }

    // Event Listeners: Dropzone & File Input
    dropzone.addEventListener("click", (event) => {
      if (isExtracting) return;
      if (event.target !== fileInput) {
        fileInput.click();
      }
    });

    dropzone.addEventListener("keydown", (event) => {
      if (isExtracting) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        resetPreviewSection();
        applySelectedFile(fileInput.files[0]);
      }
    });

    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (!isExtracting) {
        dropzone.classList.add("dragover");
      }
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
      if (isExtracting) return;

      const droppedFiles = event.dataTransfer && event.dataTransfer.files;
      if (droppedFiles && droppedFiles.length > 0) {
        resetPreviewSection();
        applySelectedFile(droppedFiles[0]);
      }
    });

    btnClearFile.addEventListener("click", () => {
      if (isExtracting) return;
      ExTraUI.hideAlert(uploadAlert);
      clearSelectedFile();
      resetPreviewSection();
    });

    previewDateInput.addEventListener("input", () => {
      if (ExTraUI.isValidIsoCalendarDate(previewDateInput.value)) {
        previewDateInput.classList.remove("input-invalid", "input-warning");
        previewDateHelp.textContent = "Format YYYY-MM-DD sesuai tanggal pada struk.";
        previewDateHelp.classList.remove("text-danger");
      }
    });

    manualDateInput.addEventListener("input", () => {
      if (ExTraUI.isValidIsoCalendarDate(manualDateInput.value)) {
        manualDateInput.classList.remove("input-invalid");
      }
    });

    // Submit Ekstraksi ke POST /api/receipts/extract
    uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (isExtracting || !selectedFile) return;

      ExTraUI.hideAlert(uploadAlert);
      resetPreviewSection();
      setExtractingState(true);

      try {
        const result = await ExTraApi.extractReceipt(selectedFile);
        openPreviewTable(result.data, result.warnings, result.temp_image_token);
      } catch (err) {
        ExTraUI.showAlert(
          uploadAlert,
          err.message || "Gagal mengekstrak foto struk. Silakan coba lagi.",
          "error"
        );
      } finally {
        setExtractingState(false);
      }
    });

    // Tambah baris item di tabel preview
    btnAddRow.addEventListener("click", () => {
      if (isSavingPreview) return;
      const newRow = createEditableItemRow(
        { name: "", price: "", category: ExTraUI.DEFAULT_CATEGORY },
        refreshPreviewSubtotal
      );
      previewTbody.appendChild(newRow);
      refreshPreviewSubtotal();
      const nameField = newRow.querySelector(".item-name-input");
      if (nameField) nameField.focus();
    });

    // Batal / Upload Ulang
    btnCancelPreview.addEventListener("click", () => {
      if (isSavingPreview) return;
      resetPreviewSection();
      clearSelectedFile();
      ExTraUI.hideAlert(uploadAlert);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    // Konfirmasi & Simpan dari Preview Struk -> POST /api/transactions
    btnSaveTransaction.addEventListener("click", async () => {
      if (isSavingPreview) return;
      ExTraUI.hideAlert(previewValidationAlert);

      const validation = collectAndValidatePayload(previewDateInput, previewTbody);
      if (validation.hasError) {
        ExTraUI.showAlert(previewValidationAlert, validation.errorMessage, "error");
        return;
      }

      setSavingPreviewState(true);
      try {
        const savePayload = {
          date: validation.date,
          items: validation.items,
        };
        if (
          previewArchiveCheckbox &&
          previewArchiveCheckbox.checked &&
          currentTempImageToken
        ) {
          savePayload.temp_image_token = currentTempImageToken;
        }
        const created = await ExTraApi.createTransaction(savePayload);
        const savedCount =
          created && created.data && Array.isArray(created.data.items)
            ? created.data.items.length
            : validation.items.length;

        resetPreviewSection();
        clearSelectedFile();
        ExTraUI.notifyDataChanged({ date: validation.date });
        ExTraUI.showToast(
          `Berhasil menyimpan ${savedCount} barang untuk tanggal ${ExTraUI.formatDateHuman(validation.date)}.`,
          "Lihat Riwayat",
          () => ExTraUI.switchTab("history")
        );
      } catch (err) {
        ExTraUI.showAlert(
          previewValidationAlert,
          err.message || "Gagal menyimpan transaksi ke database.",
          "error"
        );
      } finally {
        setSavingPreviewState(false);
      }
    });

    // Event Listeners: Input Manual
    btnAddManualRow.addEventListener("click", () => {
      if (isSavingManual) return;
      const newRow = createEditableItemRow(
        { name: "", price: "", category: ExTraUI.DEFAULT_CATEGORY },
        refreshManualSubtotal
      );
      manualTbody.appendChild(newRow);
      refreshManualSubtotal();
      const nameField = newRow.querySelector(".item-name-input");
      if (nameField) nameField.focus();
    });

    btnResetManual.addEventListener("click", () => {
      if (isSavingManual) return;
      resetManualForm();
    });

    manualForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (isSavingManual) return;
      ExTraUI.hideAlert(manualValidationAlert);

      const validation = collectAndValidatePayload(manualDateInput, manualTbody);
      if (validation.hasError) {
        ExTraUI.showAlert(manualValidationAlert, validation.errorMessage, "error");
        return;
      }

      setSavingManualState(true);
      try {
        const created = await ExTraApi.createTransaction({
          date: validation.date,
          items: validation.items,
        });
        const savedCount =
          created && created.data && Array.isArray(created.data.items)
            ? created.data.items.length
            : validation.items.length;

        resetManualForm();
        ExTraUI.notifyDataChanged({ date: validation.date });
        ExTraUI.showToast(
          `Berhasil mencatat manual ${savedCount} barang untuk tanggal ${ExTraUI.formatDateHuman(validation.date)}.`,
          "Lihat Riwayat",
          () => ExTraUI.switchTab("history")
        );
      } catch (err) {
        ExTraUI.showAlert(
          manualValidationAlert,
          err.message || "Gagal menyimpan pengeluaran manual ke database.",
          "error"
        );
      } finally {
        setSavingManualState(false);
      }
    });

    // Inisialisasi awal form Input Manual
    resetManualForm();
  });
})();
