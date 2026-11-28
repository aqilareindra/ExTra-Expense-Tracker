import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiClientError } from "../api/client";
import {
  getTransactions,
  triggerCsvExportDownload,
} from "../api/transactions";
import {
  DeleteConfirmModal,
  type DeleteTarget,
} from "../components/history/DeleteConfirmModal";
import { EditItemModal } from "../components/history/EditItemModal";
import { ReceiptViewerModal } from "../components/history/ReceiptViewerModal";
import {
  CATEGORY_COLORS,
  EXPENSE_CATEGORIES,
  type ExpenseCategory,
} from "../constants/categories";
import type { TransactionItemRecord } from "../types/api";
import {
  MONTH_NAMES_ID,
  formatDateHuman,
  formatRupiah,
} from "../utils/formatters";

interface TransactionHistoryPageProps {
  refreshKey: number;
  onDataMutated: (toastMessage: string) => void;
  onGoToEntry: () => void;
}

export function TransactionHistoryPage({
  refreshKey,
  onDataMutated,
  onGoToEntry,
}: TransactionHistoryPageProps) {
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<ExpenseCategory | "">("");
  const [monthFilter, setMonthFilter] = useState<number | "">("");
  const [yearFilter, setYearFilter] = useState<number | "">("");

  const [items, setItems] = useState<TransactionItemRecord[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [editingItem, setEditingItem] = useState<TransactionItemRecord | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [viewingReceiptItem, setViewingReceiptItem] =
    useState<TransactionItemRecord | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, 260);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const activeFilters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      category: categoryFilter || undefined,
      month: monthFilter === "" ? undefined : monthFilter,
      year: yearFilter === "" ? undefined : yearFilter,
    }),
    [debouncedSearch, categoryFilter, monthFilter, yearFilter],
  );

  const hasActiveFilters = Boolean(
    debouncedSearch ||
      categoryFilter !== "" ||
      monthFilter !== "" ||
      yearFilter !== "",
  );

  const yearOptions = useMemo(() => {
    const nowYear = new Date().getFullYear();
    const set = new Set<number>();
    for (let y = nowYear + 1; y >= 2020; y -= 1) {
      set.add(y);
    }
    items.forEach((item) => {
      if (/^\d{4}-/.test(item.date)) {
        const yr = Number(item.date.slice(0, 4));
        if (yr >= 1000 && yr <= 9999) {
          set.add(yr);
        }
      }
    });
    return Array.from(set).sort((a, b) => b - a);
  }, [items]);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const resp = await getTransactions(activeFilters);
      setItems(resp.data);
      setTotalCount(resp.count);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal memuat daftar riwayat transaksi.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [activeFilters]);

  useEffect(() => {
    void fetchHistory();
  }, [fetchHistory, refreshKey]);

  const handleSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    setDebouncedSearch(searchInput.trim());
  };

  const handleResetFilters = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setCategoryFilter("");
    setMonthFilter("");
    setYearFilter("");
  };

  const handleExportCsv = async () => {
    setErrorMessage(null);
    try {
      await triggerCsvExportDownload({
        search: searchInput.trim() || undefined,
        category: categoryFilter || undefined,
        month: monthFilter === "" ? undefined : monthFilter,
        year: yearFilter === "" ? undefined : yearFilter,
      });
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal mengunduh file CSV.";
      setErrorMessage(msg);
    }
  };

  return (
    <section aria-label="Riwayat Transaksi" className="space-y-5">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
          Riwayat Pengeluaran
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Telusuri, cari, filter kategori atau periode, koreksi, ekspor CSV,
          maupun lihat arsip foto struk tersimpan.
        </p>
      </div>

      {/* Filter & Search Card */}
      <form
        onSubmit={handleSearchSubmit}
        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <label
              htmlFor="v2-history-search"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Cari Nama Barang
            </label>
            <input
              id="v2-history-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Mis. Indomie, Kopi, Parkir..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>

          <div className="lg:col-span-3">
            <label
              htmlFor="v2-history-category"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Kategori
            </label>
            <select
              id="v2-history-category"
              value={categoryFilter}
              onChange={(e) =>
                setCategoryFilter(e.target.value as ExpenseCategory | "")
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value="">Semua Kategori</option>
              {EXPENSE_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="lg:col-span-2">
            <label
              htmlFor="v2-history-month"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Bulan
            </label>
            <select
              id="v2-history-month"
              value={monthFilter}
              onChange={(e) =>
                setMonthFilter(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value="">Semua Bulan</option>
              {MONTH_NAMES_ID.slice(1).map((name, idx) => (
                <option key={name} value={idx + 1}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div className="lg:col-span-2">
            <label
              htmlFor="v2-history-year"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Tahun
            </label>
            <select
              id="v2-history-year"
              value={yearFilter}
              onChange={(e) =>
                setYearFilter(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value="">Semua Tahun</option>
              {yearOptions.map((yr) => (
                <option key={yr} value={yr}>
                  {yr}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end lg:col-span-1">
            <button
              type="button"
              onClick={handleResetFilters}
              disabled={!hasActiveFilters}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reset
            </button>
          </div>
        </div>
      </form>

      {errorMessage ? (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={() => void fetchHistory()}
            className="self-start rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 sm:self-auto"
          >
            Coba Lagi
          </button>
        </div>
      ) : null}

      {/* History List Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs font-medium text-slate-500 sm:text-sm">
            {isLoading
              ? "Memuat riwayat transaksi..."
              : `Menampilkan ${totalCount} item tercatat`}
          </span>

          <button
            type="button"
            onClick={() => void handleExportCsv()}
            className="inline-flex items-center justify-center rounded-lg border border-brand-200 bg-brand-50 px-3.5 py-1.5 text-xs font-semibold text-brand-700 transition hover:bg-brand-100 sm:text-sm"
          >
            Ekspor CSV
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2.5 py-12 text-sm text-slate-500">
            <span
              className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
              aria-hidden="true"
            />
            <span>Mengambil riwayat transaksi...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center">
            <p className="text-base font-bold text-slate-900">
              {hasActiveFilters
                ? "Tidak ada barang yang cocok"
                : "Belum ada catatan transaksi"}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {hasActiveFilters
                ? "Coba ubah kata kunci pencarian, kategori, atau pilih periode bulan dan tahun lain."
                : "Mulai catat pengeluaran dari foto struk belanja atau input manual."}
            </p>
            <div className="mt-4">
              {hasActiveFilters ? (
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Reset Filter
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onGoToEntry}
                  className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800"
                >
                  Catat Pengeluaran Pertama
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Desktop Table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs font-bold uppercase tracking-wider text-slate-500">
                    <th className="px-3 py-3">Tanggal</th>
                    <th className="px-3 py-3">Nama Barang</th>
                    <th className="px-3 py-3">Kategori</th>
                    <th className="px-3 py-3 text-right">Harga</th>
                    <th className="px-3 py-3 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="whitespace-nowrap px-3 py-3">
                        <div className="font-medium text-slate-900">
                          {formatDateHuman(item.date)}
                        </div>
                        <div className="text-xs text-slate-400">
                          {item.date} &bull; #{item.transaction_id}
                        </div>
                      </td>
                      <td className="px-3 py-3 font-medium text-slate-900">
                        {item.name}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3">
                        <span
                          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${CATEGORY_COLORS[item.category].badgeClass}`}
                        >
                          {item.category}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right font-bold tabular-nums text-slate-900">
                        {formatRupiah(item.price)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <div className="inline-flex flex-wrap justify-end gap-1.5">
                          {item.has_receipt ? (
                            <button
                              type="button"
                              onClick={() => setViewingReceiptItem(item)}
                              className="rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 transition hover:bg-brand-100"
                            >
                              Lihat Struk
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => setEditingItem(item)}
                            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setDeleteTarget({ mode: "item", item })
                            }
                            className="rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                          >
                            Hapus
                          </button>
                          <button
                            type="button"
                            title="Hapus seluruh item dalam transaksi/struk ini"
                            onClick={() =>
                              setDeleteTarget({ mode: "transaction", item })
                            }
                            className="rounded-lg border border-red-200 bg-red-50/70 px-2.5 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-100"
                          >
                            Hapus Struk
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Card Stack (360px+) */}
            <div className="flex flex-col gap-3 md:hidden">
              {items.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="break-words text-sm font-bold text-slate-900">
                        {item.name}
                      </h3>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {formatDateHuman(item.date)} &bull; Struk #
                        {item.transaction_id}
                      </p>
                    </div>
                    <strong className="shrink-0 text-sm font-extrabold tabular-nums text-slate-900">
                      {formatRupiah(item.price)}
                    </strong>
                  </div>

                  <div className="mt-2.5">
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${CATEGORY_COLORS[item.category].badgeClass}`}
                    >
                      {item.category}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5 border-t border-slate-200 pt-2.5">
                    {item.has_receipt ? (
                      <button
                        type="button"
                        onClick={() => setViewingReceiptItem(item)}
                        className="rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1.5 text-xs font-semibold text-brand-700"
                      >
                        Lihat Struk
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => setEditingItem(item)}
                      className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget({ mode: "item", item })}
                      className="rounded-lg border border-red-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-red-600"
                    >
                      Hapus
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setDeleteTarget({ mode: "transaction", item })
                      }
                      className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs font-semibold text-red-700"
                    >
                      Hapus Struk
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Modals */}
      <EditItemModal
        item={editingItem}
        onClose={() => setEditingItem(null)}
        onUpdated={() => {
          setEditingItem(null);
          onDataMutated("Perubahan item berhasil disimpan.");
        }}
      />

      <DeleteConfirmModal
        target={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={(msg) => {
          setDeleteTarget(null);
          onDataMutated(msg);
        }}
      />

      <ReceiptViewerModal
        item={viewingReceiptItem}
        onClose={() => setViewingReceiptItem(null)}
      />
    </section>
  );
}
