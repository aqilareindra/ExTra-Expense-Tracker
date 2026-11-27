import { useEffect, useState } from "react";
import { ApiClientError } from "../../api/client";
import { deleteItem, deleteTransaction } from "../../api/transactions";
import type { TransactionItemRecord } from "../../types/api";
import { formatDateHuman, formatRupiah } from "../../utils/formatters";

export type DeleteTarget =
  | { mode: "item"; item: TransactionItemRecord }
  | { mode: "transaction"; item: TransactionItemRecord };

interface DeleteConfirmModalProps {
  target: DeleteTarget | null;
  onClose: () => void;
  onDeleted: (message: string) => void;
}

export function DeleteConfirmModal({
  target,
  onClose,
  onDeleted,
}: DeleteConfirmModalProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setErrorMessage(null);
    setIsDeleting(false);
  }, [target]);

  useEffect(() => {
    if (!target) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isDeleting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [target, isDeleting, onClose]);

  if (!target) {
    return null;
  }

  const isTransaction = target.mode === "transaction";
  const { item } = target;

  const handleConfirm = async () => {
    if (isDeleting) return;
    setErrorMessage(null);
    setIsDeleting(true);

    try {
      if (isTransaction) {
        await deleteTransaction(item.transaction_id);
        onDeleted(
          `Transaksi #${item.transaction_id} tanggal ${formatDateHuman(item.date)} beserta seluruh itemnya berhasil dihapus.`,
        );
      } else {
        await deleteItem(item.id);
        onDeleted(`Item "${item.name}" berhasil dihapus.`);
      }
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menghapus data transaksi.";
      setErrorMessage(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="v2-delete-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDeleting) {
          onClose();
        }
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl sm:p-6">
        <div className="mb-3 flex items-center justify-between">
          <h3
            id="v2-delete-modal-title"
            className="text-lg font-bold text-slate-900"
          >
            {isTransaction ? "Hapus Seluruh Struk?" : "Hapus Item Pengeluaran?"}
          </h3>
          <button
            type="button"
            disabled={isDeleting}
            onClick={onClose}
            aria-label="Tutup dialog konfirmasi"
            className="rounded-lg px-2 py-1 text-xl leading-none text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
          >
            &times;
          </button>
        </div>

        {errorMessage ? (
          <div
            role="alert"
            className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-800"
          >
            {errorMessage}
          </div>
        ) : null}

        {isTransaction ? (
          <div className="space-y-2 text-sm text-slate-600">
            <p>
              Anda akan menghapus{" "}
              <strong className="text-slate-900">
                seluruh transaksi #{item.transaction_id}
              </strong>{" "}
              pada tanggal{" "}
              <strong className="text-slate-900">
                {formatDateHuman(item.date)}
              </strong>{" "}
              beserta semua barang dan arsip foto struk (jika ada) di dalamnya.
            </p>
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Jika hanya ingin menghapus satu baris barang saja, pilih{" "}
              <strong>Batal</strong> lalu tekan tombol <strong>Hapus</strong>{" "}
              pada item tersebut.
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-600">
            Apakah Anda yakin ingin menghapus item{" "}
            <strong className="text-slate-900">"{item.name}"</strong> (
            {formatRupiah(item.price)}) pada tanggal{" "}
            <strong className="text-slate-900">
              {formatDateHuman(item.date)}
            </strong>
            ? Item lain pada transaksi yang sama tidak akan terhapus.
          </p>
        )}

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={isDeleting}
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            Batal
          </button>
          <button
            type="button"
            disabled={isDeleting}
            onClick={handleConfirm}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700 disabled:opacity-50"
          >
            {isDeleting
              ? "Menghapus..."
              : isTransaction
                ? "Ya, Hapus Struk"
                : "Ya, Hapus Item"}
          </button>
        </div>
      </div>
    </div>
  );
}
