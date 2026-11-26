import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { ApiClientError } from "../../api/client";
import { extractReceiptImage } from "../../api/receipts";
import { createTransaction } from "../../api/transactions";
import { DEFAULT_CATEGORY } from "../../constants/categories";
import type { EditableItemDraft } from "../../types/api";
import {
  createEmptyDraftRow,
  formatDateHuman,
  formatFileSize,
  isValidIsoCalendarDate,
} from "../../utils/formatters";
import { validateEntryForm } from "../../utils/validation";
import { EditableItemsList } from "./EditableItemsList";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"];
const ALLOWED_MIMES = ["image/jpeg", "image/png"];

interface ReceiptScanPanelProps {
  onSavedSuccess: (message: string) => void;
}

function validateClientImageFile(file: File): string | null {
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

export function ReceiptScanPanel({ onSavedSuccess }: ReceiptScanPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [isExtracting, setIsExtracting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [hasPreview, setHasPreview] = useState(false);
  const [previewDate, setPreviewDate] = useState("");
  const [previewDateError, setPreviewDateError] = useState<string | null>(null);
  const [previewWarnings, setPreviewWarnings] = useState<string[]>([]);
  const [previewItems, setPreviewItems] = useState<EditableItemDraft[]>([]);
  const [previewValidationError, setPreviewValidationError] = useState<string | null>(null);
  const [tempImageToken, setTempImageToken] = useState<string | null>(null);
  const [saveArchive, setSaveArchive] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    return () => {
      if (thumbnailUrl) {
        URL.revokeObjectURL(thumbnailUrl);
      }
    };
  }, [thumbnailUrl]);

  const clearPreviewState = () => {
    setHasPreview(false);
    setPreviewDate("");
    setPreviewDateError(null);
    setPreviewWarnings([]);
    setPreviewItems([]);
    setPreviewValidationError(null);
    setTempImageToken(null);
    setSaveArchive(true);
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    setThumbnailUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const applySelectedFile = (file: File) => {
    setUploadError(null);
    clearPreviewState();

    const validationMsg = validateClientImageFile(file);
    if (validationMsg) {
      clearSelectedFile();
      setUploadError(validationMsg);
      return;
    }

    const nextObjectUrl = URL.createObjectURL(file);
    setThumbnailUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return nextObjectUrl;
    });
    setSelectedFile(file);
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      applySelectedFile(file);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (isExtracting) return;
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      applySelectedFile(droppedFile);
    }
  };

  const handleExtractSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedFile || isExtracting) return;

    setUploadError(null);
    clearPreviewState();
    setIsExtracting(true);

    try {
      const result = await extractReceiptImage(selectedFile);
      const extractedDate = result.data.date ?? "";
      const mappedItems: EditableItemDraft[] =
        result.data.items.length > 0
          ? result.data.items.map((item) => ({
              ...createEmptyDraftRow(item.category),
              name: item.name,
              price: String(item.price),
            }))
          : [createEmptyDraftRow(DEFAULT_CATEGORY)];

      const token = result.temp_image_token ?? null;
      setPreviewDate(extractedDate);
      setPreviewWarnings(
        !extractedDate && result.warnings.length === 0
          ? [
              "Tanggal transaksi tidak terbaca pada struk. Silakan isi manual sebelum menyimpan.",
            ]
          : result.warnings,
      );
      if (!extractedDate) {
        setPreviewDateError(
          "Tanggal belum terbaca otomatis — wajib diisi manual sebelum menyimpan.",
        );
      }
      setPreviewItems(mappedItems);
      setTempImageToken(token);
      setSaveArchive(Boolean(token));
      setHasPreview(true);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menganalisis foto struk. Silakan coba lagi.";
      setUploadError(msg);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleUpdatePreviewRow = (
    localId: string,
    patch: Partial<Pick<EditableItemDraft, "name" | "category" | "price">>,
  ) => {
    setPreviewItems((prev) =>
      prev.map((row) =>
        row.localId === localId
          ? {
              ...row,
              ...patch,
              nameError: patch.name !== undefined ? undefined : row.nameError,
              categoryError:
                patch.category !== undefined ? undefined : row.categoryError,
              priceError: patch.price !== undefined ? undefined : row.priceError,
            }
          : row,
      ),
    );
  };

  const handleRemovePreviewRow = (localId: string) => {
    setPreviewItems((prev) => prev.filter((row) => row.localId !== localId));
  };

  const handleAddPreviewRow = () => {
    setPreviewItems((prev) => [...prev, createEmptyDraftRow(DEFAULT_CATEGORY)]);
  };

  const handleCancelPreview = () => {
    if (isSaving) return;
    clearPreviewState();
    clearSelectedFile();
    setUploadError(null);
  };

  const handleConfirmSave = async () => {
    if (isSaving) return;
    setPreviewValidationError(null);

    const validation = validateEntryForm(previewDate, previewItems);
    setPreviewItems(validation.validatedDrafts);
    setPreviewDateError(validation.dateError);

    if (!validation.isValid) {
      setPreviewValidationError(validation.bannerError);
      return;
    }

    setIsSaving(true);
    try {
      const response = await createTransaction({
        date: previewDate.trim(),
        items: validation.payloadItems,
        ...(saveArchive && tempImageToken
          ? { temp_image_token: tempImageToken }
          : {}),
      });

      const savedCount = response.data.items.length;
      const savedDate = response.data.date;

      clearPreviewState();
      clearSelectedFile();
      onSavedSuccess(
        `Berhasil menyimpan ${savedCount} barang untuk tanggal ${formatDateHuman(savedDate)}.`,
      );
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menyimpan transaksi ke database.";
      setPreviewValidationError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const isMissingDateWarning =
    hasPreview && (!previewDate || previewWarnings.length > 0);

  return (
    <div className="space-y-5">
      {uploadError ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {uploadError}
        </div>
      ) : null}

      {/* Card Upload Struk */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <form onSubmit={handleExtractSubmit} noValidate>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            onChange={handleFileInputChange}
            disabled={isExtracting}
            className="hidden"
          />

          <div
            role="button"
            tabIndex={0}
            aria-label="Klik atau tarik dan lepas foto struk belanja di sini"
            onClick={() => {
              if (!isExtracting) fileInputRef.current?.click();
            }}
            onKeyDown={(e) => {
              if (!isExtracting && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              if (!isExtracting) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-7 text-center transition focus:outline-none focus:ring-2 focus:ring-brand-200 ${
              isExtracting ? "pointer-events-none opacity-60" : ""
            } ${
              isDragging
                ? "border-brand-700 bg-brand-50"
                : "border-slate-300 bg-slate-50/70 hover:border-brand-600 hover:bg-brand-50/50"
            }`}
          >
            {selectedFile && thumbnailUrl ? (
              <div className="flex flex-col items-center justify-center gap-4 text-left sm:flex-row">
                <img
                  src={thumbnailUrl}
                  alt="Pratinjau foto struk belanja"
                  className="max-h-48 max-w-[220px] rounded-lg border border-slate-200 bg-white object-contain p-1 shadow-sm"
                />
                <div className="text-center sm:text-left">
                  <p className="break-all text-sm font-semibold text-slate-900">
                    {selectedFile.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {formatFileSize(selectedFile.size)}
                  </p>
                  <p className="mt-2 text-xs font-medium text-brand-700">
                    Siap dianalisis oleh Gemini Vision
                  </p>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-md space-y-2">
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-brand-700">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-slate-800">
                  Klik untuk memilih foto struk atau tarik &amp; lepas ke sini
                </p>
                <p className="text-xs text-slate-500">
                  Format didukung: JPG, JPEG, PNG &bull; Ukuran maksimal 5 MB
                </p>
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap gap-2.5">
            <button
              type="submit"
              disabled={!selectedFile || isExtracting}
              className="inline-flex items-center justify-center rounded-lg bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isExtracting ? "Menganalisis..." : "Analisis Struk"}
            </button>

            {selectedFile ? (
              <button
                type="button"
                disabled={isExtracting}
                onClick={() => {
                  clearSelectedFile();
                  clearPreviewState();
                  setUploadError(null);
                }}
                className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
              >
                Pilih Gambar Lain
              </button>
            ) : null}
          </div>

          {isExtracting ? (
            <div
              aria-live="polite"
              className="mt-4 flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800"
            >
              <span
                className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
                aria-hidden="true"
              />
              <div>
                <p className="font-semibold">Menganalisis struk...</p>
                <p className="text-xs text-slate-600">
                  Gambar sedang dikompresi &amp; dibaca oleh Gemini Vision. Mohon tunggu.
                </p>
              </div>
            </div>
          ) : null}
        </form>
      </div>

      {/* Tabel Preview Editable (Human-in-the-Loop) */}
      {hasPreview ? (
        <div className="rounded-2xl border border-brand-200 bg-white p-4 shadow-md sm:p-6">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-900 sm:text-lg">
                Pratinjau &amp; Verifikasi Hasil Ekstraksi
              </h3>
              <p className="mt-0.5 text-xs text-slate-600 sm:text-sm">
                Periksa dan koreksi tanggal, nama barang, kategori, atau harga sebelum menekan{" "}
                <strong>Konfirmasi &amp; Simpan</strong>.
              </p>
            </div>
            <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
              Belum Tersimpan
            </span>
          </div>

          {isMissingDateWarning ? (
            <div
              role="alert"
              className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            >
              {previewWarnings.join(" ")}
            </div>
          ) : null}

          {previewValidationError ? (
            <div
              role="alert"
              className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {previewValidationError}
            </div>
          ) : null}

          <div className="mb-5 max-w-xs">
            <label
              htmlFor="v2-preview-date"
              className="mb-1.5 block text-sm font-semibold text-slate-800"
            >
              Tanggal Transaksi <span className="text-red-600">*</span>
            </label>
            <input
              id="v2-preview-date"
              type="date"
              value={previewDate}
              disabled={isSaving}
              onChange={(e) => {
                const nextVal = e.target.value;
                setPreviewDate(nextVal);
                if (isValidIsoCalendarDate(nextVal)) {
                  setPreviewDateError(null);
                }
              }}
              className={`w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 ${
                previewDateError
                  ? "border-red-500 bg-amber-50 focus:ring-red-200"
                  : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
              }`}
            />
            <p
              className={`mt-1 text-xs ${
                previewDateError ? "font-semibold text-red-600" : "text-slate-500"
              }`}
            >
              {previewDateError ?? "Format YYYY-MM-DD sesuai tanggal pada struk."}
            </p>
          </div>

          <EditableItemsList
            items={previewItems}
            disabled={isSaving}
            addLabel="+ Tambah Barang"
            estimateLabel="Estimasi Total Preview"
            onUpdateRow={handleUpdatePreviewRow}
            onRemoveRow={handleRemovePreviewRow}
            onAddRow={handleAddPreviewRow}
          />

          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3">
            <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm font-semibold text-slate-800">
              <input
                type="checkbox"
                checked={saveArchive}
                disabled={isSaving || !tempImageToken}
                onChange={(e) => setSaveArchive(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-600"
              />
              <span>Simpan arsip foto struk</span>
            </label>
            <p className="mt-1 pl-6 text-xs text-slate-500">
              Menyimpan salinan foto struk terkompresi agar dapat dilihat kembali di Riwayat.
            </p>
          </div>

          <div className="mt-5 flex flex-col-reverse gap-2.5 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              disabled={isSaving}
              onClick={handleCancelPreview}
              className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
            >
              Batal / Upload Ulang
            </button>
            <button
              type="button"
              disabled={isSaving}
              onClick={handleConfirmSave}
              className="inline-flex items-center justify-center rounded-lg bg-brand-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:opacity-50"
            >
              {isSaving ? "Menyimpan..." : "Konfirmasi & Simpan"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
