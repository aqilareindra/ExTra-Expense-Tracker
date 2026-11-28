import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  createIncome,
  deleteBudget,
  deleteIncome,
  getBudgets,
  getIncomes,
  upsertBudget,
} from "../api/budgets";
import { ApiClientError } from "../api/client";
import {
  CATEGORY_COLORS,
  EXPENSE_CATEGORIES,
  type ExpenseCategory,
} from "../constants/categories";
import type {
  BudgetListResponse,
  BudgetStatus,
  BudgetStatusItem,
  IncomeListResponse,
} from "../types/api";
import {
  MONTH_NAMES_ID,
  formatDateHuman,
  formatRupiah,
  getMonthName,
  getTodayIsoDate,
  isValidIsoCalendarDate,
  parseStrictNonNegativeInt,
} from "../utils/formatters";

interface BudgetsAndIncomePageProps {
  refreshKey: number;
  onDataMutated: (toastMessage: string) => void;
}

const BUDGET_STATUS_STYLES: Record<
  BudgetStatus,
  { label: string; badgeClass: string; barClass: string }
> = {
  safe: {
    label: "Aman",
    badgeClass: "border-emerald-200 bg-emerald-50 text-emerald-800",
    barClass: "bg-emerald-600",
  },
  warning: {
    label: "Mendekati Batas",
    badgeClass: "border-amber-200 bg-amber-50 text-amber-800",
    barClass: "bg-amber-500",
  },
  over_budget: {
    label: "Melebihi Anggaran",
    badgeClass: "border-rose-200 bg-rose-50 text-rose-800",
    barClass: "bg-rose-600",
  },
};

export function BudgetsAndIncomePage({
  refreshKey,
  onDataMutated,
}: BudgetsAndIncomePageProps) {
  const now = useMemo(() => new Date(), []);
  const [month, setMonth] = useState<number>(() => now.getMonth() + 1);
  const [year, setYear] = useState<number>(() =>
    Math.min(2100, Math.max(2000, now.getFullYear())),
  );

  const [budgetsData, setBudgetsData] = useState<BudgetListResponse | null>(null);
  const [incomesData, setIncomesData] = useState<IncomeListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Budget Form State
  const [budgetCategory, setBudgetCategory] = useState<ExpenseCategory>(
    EXPENSE_CATEGORIES[0],
  );
  const [budgetLimitInput, setBudgetLimitInput] = useState("");
  const [budgetFormError, setBudgetFormError] = useState<string | null>(null);
  const [isSavingBudget, setIsSavingBudget] = useState(false);

  // Income Form State
  const [incomeDate, setIncomeDate] = useState(() => getTodayIsoDate());
  const [incomeSource, setIncomeSource] = useState("");
  const [incomeAmountInput, setIncomeAmountInput] = useState("");
  const [incomeFormError, setIncomeFormError] = useState<string | null>(null);
  const [isSavingIncome, setIsSavingIncome] = useState(false);

  // Delete confirmation state
  const [confirmDeleteIncomeId, setConfirmDeleteIncomeId] = useState<number | null>(
    null,
  );
  const [confirmDeleteBudgetId, setConfirmDeleteBudgetId] = useState<number | null>(
    null,
  );
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);

  const yearOptions = useMemo(() => {
    const currentYear = Math.min(2100, Math.max(2000, now.getFullYear()));
    const maxYear = Math.min(2100, currentYear + 2);
    const list: number[] = [];
    for (let y = maxYear; y >= 2020; y -= 1) {
      list.push(y);
    }
    return list;
  }, [now]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [budgetsResp, incomesResp] = await Promise.all([
        getBudgets(month, year),
        getIncomes(month, year),
      ]);
      setBudgetsData(budgetsResp);
      setIncomesData(incomesResp);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal memuat data anggaran dan pemasukan.";
      setLoadError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [month, year]);

  useEffect(() => {
    void loadData();
  }, [loadData, refreshKey]);

  const periodLabel = `${getMonthName(month)} ${year}`;

  const handleSaveBudget = async (event: FormEvent) => {
    event.preventDefault();
    setBudgetFormError(null);

    const parsedLimit = parseStrictNonNegativeInt(budgetLimitInput);
    if (parsedLimit === null) {
      setBudgetFormError("Batas anggaran harus berupa bilangan bulat minimal 0.");
      return;
    }

    setIsSavingBudget(true);
    try {
      await upsertBudget({
        month,
        year,
        category: budgetCategory,
        limit_amount: parsedLimit,
      });
      setBudgetLimitInput("");
      onDataMutated(
        `Anggaran "${budgetCategory}" (${periodLabel}) berhasil disimpan.`,
      );
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menyimpan batas anggaran.";
      setBudgetFormError(msg);
    } finally {
      setIsSavingBudget(false);
    }
  };

  const handleSelectBudgetForEdit = (item: BudgetStatusItem) => {
    setBudgetCategory(item.category);
    setBudgetLimitInput(String(item.limit_amount));
    setBudgetFormError(null);
  };

  const handleDeleteBudget = async (budgetId: number) => {
    setIsDeletingId(`budget-${budgetId}`);
    try {
      await deleteBudget(budgetId);
      setConfirmDeleteBudgetId(null);
      onDataMutated("Batas anggaran kategori berhasil dihapus.");
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menghapus batas anggaran.";
      setLoadError(msg);
    } finally {
      setIsDeletingId(null);
    }
  };

  const handleSaveIncome = async (event: FormEvent) => {
    event.preventDefault();
    setIncomeFormError(null);

    const trimmedDate = incomeDate.trim();
    if (!isValidIsoCalendarDate(trimmedDate)) {
      setIncomeFormError("Tanggal pemasukan harus berupa tanggal kalender valid.");
      return;
    }

    const trimmedSource = incomeSource.trim();
    if (!trimmedSource) {
      setIncomeFormError("Sumber pemasukan wajib diisi.");
      return;
    }

    const parsedAmount = parseStrictNonNegativeInt(incomeAmountInput);
    if (parsedAmount === null) {
      setIncomeFormError("Nominal pemasukan harus berupa bilangan bulat minimal 0.");
      return;
    }

    setIsSavingIncome(true);
    try {
      await createIncome({
        income_date: trimmedDate,
        source_name: trimmedSource,
        amount: parsedAmount,
      });
      setIncomeSource("");
      setIncomeAmountInput("");
      const [yStr, mStr] = trimmedDate.split("-");
      const savedYear = Number(yStr);
      const savedMonth = Number(mStr);
      if (savedYear >= 2000 && savedYear <= 2100 && savedMonth >= 1 && savedMonth <= 12) {
        setYear(savedYear);
        setMonth(savedMonth);
      }
      onDataMutated(`Pemasukan "${trimmedSource}" berhasil dicatat.`);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal mencatat pemasukan.";
      setIncomeFormError(msg);
    } finally {
      setIsSavingIncome(false);
    }
  };

  const handleDeleteIncome = async (incomeId: number) => {
    setIsDeletingId(`income-${incomeId}`);
    try {
      await deleteIncome(incomeId);
      setConfirmDeleteIncomeId(null);
      onDataMutated("Catatan pemasukan berhasil dihapus.");
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menghapus catatan pemasukan.";
      setLoadError(msg);
    } finally {
      setIsDeletingId(null);
    }
  };

  return (
    <section aria-label="Anggaran dan Pemasukan" className="space-y-6">
      {/* Header & Period Filter */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            Anggaran &amp; Pemasukan
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Atur batas anggaran bulanan per kategori dan catat sumber pemasukan
            untuk memantau arus kas bersih.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:flex sm:items-end">
          <div>
            <label
              htmlFor="v2-budget-month"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Bulan
            </label>
            <select
              id="v2-budget-month"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200 sm:min-w-[140px]"
            >
              {MONTH_NAMES_ID.slice(1).map((name, idx) => (
                <option key={name} value={idx + 1}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="v2-budget-year"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Tahun
            </label>
            <select
              id="v2-budget-year"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200 sm:min-w-[110px]"
            >
              {yearOptions.map((yr) => (
                <option key={yr} value={yr}>
                  {yr}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loadError ? (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{loadError}</span>
          <button
            type="button"
            onClick={() => void loadData()}
            className="self-start rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 sm:self-auto"
          >
            Muat Ulang
          </button>
        </div>
      ) : null}

      {/* =================================================================== */}
      {/* BAGIAN 1: ANGGARAN BULANAN PER KATEGORI                             */}
      {/* =================================================================== */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              Anggaran Bulanan ({periodLabel})
            </h3>
            <p className="text-xs text-slate-500 sm:text-sm">
              Tetapkan batas belanja per kategori. Indikator berubah kuning saat
              &ge; 80% dan merah saat melewati batas.
            </p>
          </div>

          {budgetsData && budgetsData.data.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs tabular-nums">
              <span className="text-slate-500">Total Terpakai: </span>
              <strong className="text-slate-900">
                {formatRupiah(budgetsData.total_spent)}
              </strong>
              <span className="text-slate-400"> / </span>
              <strong className="text-brand-700">
                {formatRupiah(budgetsData.total_budget)}
              </strong>
            </div>
          ) : null}
        </div>

        {/* Form Upsert Budget */}
        <form
          onSubmit={(e) => void handleSaveBudget(e)}
          className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 sm:p-4"
          noValidate
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-12 sm:items-end">
            <div className="sm:col-span-5">
              <label
                htmlFor="v2-budget-category-input"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Kategori Pengeluaran
              </label>
              <select
                id="v2-budget-category-input"
                value={budgetCategory}
                onChange={(e) =>
                  setBudgetCategory(e.target.value as ExpenseCategory)
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              >
                {EXPENSE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-4">
              <label
                htmlFor="v2-budget-limit-input"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Batas Anggaran (Rp)
              </label>
              <input
                id="v2-budget-limit-input"
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                value={budgetLimitInput}
                onChange={(e) => setBudgetLimitInput(e.target.value)}
                placeholder="Mis. 500000"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm tabular-nums text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div className="sm:col-span-3">
              <button
                type="submit"
                disabled={isSavingBudget}
                className="w-full rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSavingBudget ? "Menyimpan..." : "Simpan Anggaran"}
              </button>
            </div>
          </div>

          {budgetFormError ? (
            <p role="alert" className="mt-2 text-xs font-medium text-red-700">
              {budgetFormError}
            </p>
          ) : null}
        </form>

        {/* Budget Progress List */}
        <div className="mt-4">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-slate-500">
              <span
                className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
                aria-hidden="true"
              />
              <span>Memuat status anggaran...</span>
            </div>
          ) : !budgetsData || budgetsData.data.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center">
              <p className="text-sm font-semibold text-slate-800">
                Belum ada batas anggaran untuk {periodLabel}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Pilih kategori dan masukkan batas nominal di atas untuk mulai
                memantau pemakaian anggaran.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {budgetsData.data.map((item) => {
                const statusMeta = BUDGET_STATUS_STYLES[item.status];
                const barWidth = Math.min(100, Math.max(0, item.usage_percentage));
                const isConfirming = confirmDeleteBudgetId === item.id;

                return (
                  <article
                    key={item.id}
                    className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5 sm:p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${CATEGORY_COLORS[item.category].badgeClass}`}
                        >
                          {item.category}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusMeta.badgeClass}`}
                        >
                          {statusMeta.label} ({item.usage_percentage.toFixed(1)}%)
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleSelectBudgetForEdit(item)}
                          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                        >
                          Ubah
                        </button>
                        {isConfirming ? (
                          <div className="inline-flex items-center gap-1">
                            <button
                              type="button"
                              disabled={isDeletingId === `budget-${item.id}`}
                              onClick={() => void handleDeleteBudget(item.id)}
                              className="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                            >
                              Ya, Hapus
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteBudgetId(null)}
                              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-600"
                            >
                              Batal
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteBudgetId(item.id)}
                            className="rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                          >
                            Hapus
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-full rounded-full transition-all ${statusMeta.barClass}`}
                        style={{ width: `${barWidth.toFixed(1)}%` }}
                      />
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-xs tabular-nums">
                      <span className="text-slate-600">
                        Terpakai{" "}
                        <strong className="text-slate-900">
                          {formatRupiah(item.spent_amount)}
                        </strong>{" "}
                        dari{" "}
                        <strong className="text-slate-900">
                          {formatRupiah(item.limit_amount)}
                        </strong>
                      </span>
                      <span
                        className={`font-semibold ${
                          item.remaining_amount < 0
                            ? "text-rose-700"
                            : "text-emerald-700"
                        }`}
                      >
                        {item.remaining_amount < 0
                          ? `Lewat ${formatRupiah(Math.abs(item.remaining_amount))}`
                          : `Sisa ${formatRupiah(item.remaining_amount)}`}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* =================================================================== */}
      {/* BAGIAN 2: PENCATATAN PEMASUKAN                                      */}
      {/* =================================================================== */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              Pemasukan ({periodLabel})
            </h3>
            <p className="text-xs text-slate-500 sm:text-sm">
              Catat gaji, uang saku, bonus, atau pemasukan lainnya untuk
              perhitungan arus kas bersih.
            </p>
          </div>

          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-xs tabular-nums">
            <span className="text-emerald-700">Total Pemasukan: </span>
            <strong className="text-sm font-extrabold text-emerald-800">
              {formatRupiah(incomesData?.total_income ?? 0)}
            </strong>
          </div>
        </div>

        {/* Form Tambah Pemasukan */}
        <form
          onSubmit={(e) => void handleSaveIncome(e)}
          className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 sm:p-4"
          noValidate
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-12 sm:items-end">
            <div className="sm:col-span-3">
              <label
                htmlFor="v2-income-date"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Tanggal
              </label>
              <input
                id="v2-income-date"
                type="date"
                value={incomeDate}
                onChange={(e) => setIncomeDate(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div className="sm:col-span-4">
              <label
                htmlFor="v2-income-source"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Sumber Pemasukan
              </label>
              <input
                id="v2-income-source"
                type="text"
                maxLength={200}
                value={incomeSource}
                onChange={(e) => setIncomeSource(e.target.value)}
                placeholder="Mis. Gaji Bulanan, Freelance"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div className="sm:col-span-3">
              <label
                htmlFor="v2-income-amount"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Nominal (Rp)
              </label>
              <input
                id="v2-income-amount"
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                value={incomeAmountInput}
                onChange={(e) => setIncomeAmountInput(e.target.value)}
                placeholder="Mis. 3500000"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm tabular-nums text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={isSavingIncome}
                className="w-full rounded-lg bg-brand-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSavingIncome ? "Menyimpan..." : "Tambah"}
              </button>
            </div>
          </div>

          {incomeFormError ? (
            <p role="alert" className="mt-2 text-xs font-medium text-red-700">
              {incomeFormError}
            </p>
          ) : null}
        </form>

        {/* Income List */}
        <div className="mt-4">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-slate-500">
              <span
                className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
                aria-hidden="true"
              />
              <span>Memuat daftar pemasukan...</span>
            </div>
          ) : !incomesData || incomesData.data.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center">
              <p className="text-sm font-semibold text-slate-800">
                Belum ada catatan pemasukan pada {periodLabel}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Tambahkan pemasukan menggunakan form di atas untuk menghitung
                arus kas bersih bulanan.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 rounded-xl border border-slate-200">
              {incomesData.data.map((inc) => {
                const isConfirming = confirmDeleteIncomeId === inc.id;
                return (
                  <div
                    key={inc.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-3 sm:px-4"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-900">
                        {inc.source_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDateHuman(inc.income_date)} ({inc.income_date})
                      </p>
                    </div>

                    <div className="flex items-center gap-2.5">
                      <strong className="text-sm font-extrabold tabular-nums text-emerald-700">
                        +{formatRupiah(inc.amount)}
                      </strong>

                      {isConfirming ? (
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            disabled={isDeletingId === `income-${inc.id}`}
                            onClick={() => void handleDeleteIncome(inc.id)}
                            className="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                          >
                            Ya, Hapus
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteIncomeId(null)}
                            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-600"
                          >
                            Batal
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteIncomeId(inc.id)}
                          className="rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                        >
                          Hapus
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
