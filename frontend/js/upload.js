/**
 * upload.js — Logika unggah foto struk, indikator loading, tabel preview editable,
 * serta konfirmasi penyimpanan eksplisit (Human-in-the-Loop).
 */
(function () {
  "use strict";

  const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
  const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"];
  const ALLOWED_MIMES = ["image/jpeg", "image/png"];

  document.addEventListener("DOMContentLoaded", () => {
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

    const previewSection = document.getElementById("preview-section");
    const previewWarningBanner = document.getElementById("preview-warning-banner");
    const previewValidationAlert = document.getElementById("preview-validation-alert");
    const previewDateInput = document.getElementById("preview-date-input");
    const previewDateHelp = document.getElementById("preview-date-help");
    const previewTbody = document.getElementById("preview-items-tbody");
    const previewTotalDisplay = document.getElementById("preview-total-display");

    const btnAddRow = document.getElementById("btn-add-preview-row");
    const btnCancelPreview = document.getElementById("btn-cancel-preview");
    const btnSaveTransaction = document.getElementById("btn-save-transaction");

    let selectedFile = null;
    let currentObjectUrl = null;
    let isExtracting = false;
    let isSaving = false;

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

    function resetPreviewSection() {
      previewSection.hidden = true;
      previewTbody.replaceChildren();
      previewDateInput.value = "";
      previewDateInput.classList.remove("input-invalid", "input-warning");
      previewDateHelp.textContent = "Format YYYY-MM-DD sesuai tanggal pada struk.";
      previewDateHelp.classList.remove("text-danger");
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

    function setSavingState(active) {
      isSaving = active;
      btnSaveTransaction.disabled = active;
      btnCancelPreview.disabled = active;
      btnAddRow.disabled = active;
      btnSaveTransaction.textContent = active
        ? "Menyimpan..."
        : "Konfirmasi & Simpan";
    }

    function refreshRowNumbersAndSubtotal() {
      const rows = previewTbody.querySelectorAll("tr.preview-item-row");
      let total = 0;
      rows.forEach((row, index) => {
        const numCell = row.querySelector(".col-num");
        if (numCell) {
          numCell.textContent = String(index + 1);
        }
        const priceInput = row.querySelector(".preview-price-input");
        const parsed = ExTraUI.parseStrictNonNegativeInt(priceInput ? priceInput.value : "");
        if (parsed !== null) {
          total += parsed;
        }
      });
      previewTotalDisplay.textContent = ExTraUI.formatRupiah(total);
    }

    function createPreviewRow(item = { name: "", price: "" }) {
      const tr = document.createElement("tr");
      tr.className = "preview-item-row";

      const tdNum = document.createElement("td");
      tdNum.className = "col-num";

      const tdName = document.createElement("td");
      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.className = "form-control preview-name-input";
      nameInput.placeholder = "Nama barang";
      nameInput.value = item.name != null ? String(item.name) : "";
      nameInput.maxLength = 200;
      nameInput.addEventListener("input", () => {
        nameInput.classList.remove("input-invalid");
      });
      tdName.appendChild(nameInput);

      const tdPrice = document.createElement("td");
      const priceInput = document.createElement("input");
      priceInput.type = "number";
      priceInput.className = "form-control preview-price-input";
      priceInput.placeholder = "0";
      priceInput.min = "0";
      priceInput.step = "1";
      priceInput.value = item.price !== undefined && item.price !== null && item.price !== ""
        ? String(item.price)
        : "";
      priceInput.addEventListener("input", () => {
        priceInput.classList.remove("input-invalid");
        refreshRowNumbersAndSubtotal();
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
        refreshRowNumbersAndSubtotal();
      });
      tdAction.appendChild(removeBtn);

      tr.append(tdNum, tdName, tdPrice, tdAction);
      return tr;
    }

    function openPreviewTable(extractedData, warnings) {
      resetPreviewSection();

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
        previewTbody.appendChild(createPreviewRow({ name: "", price: "" }));
      } else {
        items.forEach((item) => {
          previewTbody.appendChild(createPreviewRow(item));
        });
      }

      refreshRowNumbersAndSubtotal();
      previewSection.hidden = false;
      previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
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

    // Submit Ekstraksi ke POST /api/receipts/extract
    uploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (isExtracting || !selectedFile) return;

      ExTraUI.hideAlert(uploadAlert);
      resetPreviewSection();
      setExtractingState(true);

      try {
        const result = await ExTraApi.extractReceipt(selectedFile);
        openPreviewTable(result.data, result.warnings);
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

    // Tambah baris item manual di tabel preview
    btnAddRow.addEventListener("click", () => {
      if (isSaving) return;
      const newRow = createPreviewRow({ name: "", price: "" });
      previewTbody.appendChild(newRow);
      refreshRowNumbersAndSubtotal();
      const nameField = newRow.querySelector(".preview-name-input");
      if (nameField) nameField.focus();
    });

    // Batal / Upload Ulang
    btnCancelPreview.addEventListener("click", () => {
      if (isSaving) return;
      resetPreviewSection();
      clearSelectedFile();
      ExTraUI.hideAlert(uploadAlert);
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    // Konfirmasi & Simpan ke POST /api/transactions
    btnSaveTransaction.addEventListener("click", async () => {
      if (isSaving) return;
      ExTraUI.hideAlert(previewValidationAlert);

      const dateVal = (previewDateInput.value || "").trim();
      let hasError = false;
      const errorMessages = [];

      if (!ExTraUI.isValidIsoCalendarDate(dateVal)) {
        previewDateInput.classList.add("input-invalid");
        errorMessages.push("Tanggal transaksi wajib diisi dengan tanggal kalender yang valid.");
        hasError = true;
      } else {
        previewDateInput.classList.remove("input-invalid");
      }

      const rowElements = Array.from(
        previewTbody.querySelectorAll("tr.preview-item-row")
      );
      if (rowElements.length === 0) {
        errorMessages.push("Daftar barang minimal harus berisi 1 item.");
        hasError = true;
      }

      const validatedItems = [];
      rowElements.forEach((row, idx) => {
        const nameInput = row.querySelector(".preview-name-input");
        const priceInput = row.querySelector(".preview-price-input");

        const trimmedName = (nameInput.value || "").trim();
        const parsedPrice = ExTraUI.parseStrictNonNegativeInt(priceInput.value);

        if (!trimmedName) {
          nameInput.classList.add("input-invalid");
          errorMessages.push(`Baris #${idx + 1}: Nama barang tidak boleh kosong.`);
          hasError = true;
        } else {
          nameInput.classList.remove("input-invalid");
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

        if (trimmedName && parsedPrice !== null) {
          validatedItems.push({ name: trimmedName, price: parsedPrice });
        }
      });

      if (hasError) {
        ExTraUI.showAlert(previewValidationAlert, errorMessages[0], "error");
        return;
      }

      setSavingState(true);
      try {
        const created = await ExTraApi.createTransaction({
          date: dateVal,
          items: validatedItems,
        });
        const savedCount =
          created && created.data && Array.isArray(created.data.items)
            ? created.data.items.length
            : validatedItems.length;

        resetPreviewSection();
        clearSelectedFile();
        ExTraUI.notifyDataChanged({ date: dateVal });
        ExTraUI.showToast(
          `Berhasil menyimpan ${savedCount} barang untuk tanggal ${ExTraUI.formatDateHuman(dateVal)}.`,
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
        setSavingState(false);
      }
    });
  });
})();
