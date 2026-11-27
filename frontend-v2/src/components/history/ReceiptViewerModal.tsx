import { useEffect, useState } from "react";
import { getTransactionReceiptUrl } from "../../api/transactions";
import type { TransactionItemRecord } from "../../types/api";
import { formatDateHuman } from "../../utils/formatters";

interface ReceiptViewerModalProps {
  item: TransactionItemRecord | null;
  onClose: () => void;
}

export function ReceiptViewerModal({ item, onClose }: ReceiptViewerModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (!item) return;
    setIsLoading(true);
    setHasError(false);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [item, onClose]);

  if (!item) {
    return null;
  }

  const imageUrl = getTransactionReceiptUrl(item.transaction_id);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="v2-receipt-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs"
    >
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl sm:p-6">
        <div className="mb-2 flex items-start justify-between gap-3">
          <div>
            <h3
              id="v2-receipt-modal-title"
              className="text-lg font-bold text-slate-900"
            >
              Arsip Foto Struk
            </h3>
            <p className="text-xs text-slate-500">
              Transaksi #{item.transaction_id} &bull;{" "}
              {formatDateHuman(item.date)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup modal foto struk"
            className="rounded-lg px-2 py-1 text-xl leading-none text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          >
            &times;
          </button>
        </div>

        {hasError ? (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800"
          >
            Gagal memuat arsip foto struk. File mungkin sudah tidak tersedia di
            server.
          </div>
        ) : (
          <div className="mt-3 max-h-[70vh] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-2 text-center">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
                <span
                  className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-700"
                  aria-hidden="true"
                />
                <span>Memuat foto struk...</span>
              </div>
            ) : null}
            <img
              src={imageUrl}
              alt={`Arsip foto struk transaksi #${item.transaction_id}`}
              onLoad={() => {
                setIsLoading(false);
                setHasError(false);
              }}
              onError={() => {
                setIsLoading(false);
                setHasError(true);
              }}
              className={`mx-auto max-w-full rounded-lg shadow-sm ${
                isLoading ? "hidden" : "block"
              }`}
            />
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
