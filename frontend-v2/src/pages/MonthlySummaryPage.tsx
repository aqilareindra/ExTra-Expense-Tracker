import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMonthlyInsights } from "../api/budgets";
import { ApiClientError } from "../api/client";
import { getMonthlySummary } from "../api/summary";
import { CATEGORY_COLORS } from "../constants/categories";
import type {
  MonthlyInsightsResponse,
  MonthlySummaryResponse,
} from "../types/api";
import {
  MONTH_NAMES_ID,
  formatCompactRupiah,
  formatDateHuman,
  formatRupiah,
  getMonthName,
} from "../utils/formatters";

interface MonthlySummaryPageProps {
  refreshKey: number;
  onGoToEntry: () => void;
}

interface DailyTooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{
    payload?: {
      date: string;
      total: number;
      item_count: number;
    };
  }>;
}

function DailyChartTooltip({ active, payload }: DailyTooltipProps) {
  const point = active && payload && payload[0] ? payload[0].payload : undefined;
  if (!point) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-bold text-slate-900">{formatDateHuman(point.date)}</p>
      <p className="mt-1 font-semibold tabular-nums text-brand-700">
        {formatRupiah(point.total)}
      </p>
      <p className="text-slate-500">{point.item_count} barang</p>
    </div>
  );
}

interface CategoryTooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<{
    payload?: {
      category: string;
      total: number;
      item_count: number;
    };
  }>;
}

function CategoryChartTooltip({ active, payload }: CategoryTooltipProps) {
  const point = active && payload && payload[0] ? payload[0].payload : undefined;
  if (!point) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-bold text-slate-900">{point.category}</p>
      <p className="mt-1 font-semibold tabular-nums text-brand-700">
        {formatRupiah(point.total)}
      </p>
      <p className="text-slate-500">{point.item_count} barang</p>
    </div>
  );
}

export function MonthlySummaryPage({
  refreshKey,
  onGoToEntry,
}: MonthlySummaryPageProps) {
  const now = useMemo(() => new Date(), []);
  const [month, setMonth] = useState<number>(() => now.getMonth() + 1);
  const [year, setYear] = useState<number>(() =>
    Math.min(2100, Math.max(2000, now.getFullYear())),
  );

  const [summary, setSummary] = useState<MonthlySummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [insights, setInsights] = useState<MonthlyInsightsResponse | null>(null);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  const yearOptions = useMemo(() => {
    const currentYear = Math.min(2100, Math.max(2000, now.getFullYear()));
    const maxYear = Math.min(2100, currentYear + 2);
    const list: number[] = [];
    for (let y = maxYear; y >= 2020; y -= 1) {
      list.push(y);
    }
    return list;
  }, [now]);

  const loadSummary = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await getMonthlySummary(month, year);
      setSummary(data);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal memuat ringkasan pengeluaran bulanan.";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [month, year]);

  useEffect(() => {
    setInsights(null);
    setInsightsError(null);
    void loadSummary();
  }, [loadSummary, refreshKey]);

  const handleAnalyzeInsights = async () => {
    setIsLoadingInsights(true);
    setInsightsError(null);
    try {
      const resp = await getMonthlyInsights(month, year);
      setInsights(resp);
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Gagal menghasilkan analisis keuangan AI.";
      setInsightsError(msg);
    } finally {
      setIsLoadingInsights(false);
    }
  };

  const topCategory = summary?.category_breakdown[0] ?? null;
  const periodLabel = `${getMonthName(month)} ${year}`;

  const dailyChartData = useMemo(
    () =>
      (summary?.daily_breakdown ?? []).map((entry) => ({
        ...entry,
        shortDate:
          entry.date.length === 10
            ? `${entry.date.slice(8, 10)}/${entry.date.slice(5, 7)}`
            : entry.date,
      })),
    [summary],
  );

  const hasData = Boolean(
    summary && summary.total_items > 0 && summary.daily_breakdown.length > 0,
  );

  return (
    <section aria-label="Ringkasan Bulanan" className="space-y-5">
      {/* Top Bar & Period Selector */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            Ringkasan Pengeluaran Bulanan
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Rekapitulasi deterministik total pengeluaran, rincian kategori, dan
            tren harian.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:flex sm:items-end">
          <div>
            <label
              htmlFor="v2-summary-month"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Bulan
            </label>
            <select
              id="v2-summary-month"
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
              htmlFor="v2-summary-year"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Tahun
            </label>
            <select
              id="v2-summary-year"
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

      {errorMessage ? (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={() => void loadSummary()}
            className="self-start rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 sm:self-auto"
          >
            Muat Ulang
          </button>
        </div>
      ) : null}

      {/* Metric Cards (100% dari backend) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Total Pemasukan
          </span>
          <strong className="mt-1.5 block text-2xl font-extrabold tracking-tight tabular-nums text-emerald-700">
            {summary ? formatRupiah(summary.total_income) : "Rp 0"}
          </strong>
          <span className="mt-1 block text-xs text-slate-500">
            Periode {periodLabel}
          </span>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Total Pengeluaran
          </span>
          <strong className="mt-1.5 block text-2xl font-extrabold tracking-tight tabular-nums text-slate-900">
            {summary ? formatRupiah(summary.total_expense) : "Rp 0"}
          </strong>
          <span className="mt-1 block text-xs text-slate-500">
            {summary ? `${summary.total_items} barang tercatat` : "0 barang tercatat"}
          </span>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Arus Kas Bersih
          </span>
          <strong
            className={`mt-1.5 block text-2xl font-extrabold tracking-tight tabular-nums ${
              !summary || summary.net_balance === 0
                ? "text-slate-900"
                : summary.net_balance > 0
                  ? "text-emerald-700"
                  : "text-rose-700"
            }`}
          >
            {summary ? formatRupiah(summary.net_balance) : "Rp 0"}
          </strong>
          <span className="mt-1 block text-xs text-slate-500">
            {!summary || summary.net_balance === 0
              ? "Pemasukan dikurangi pengeluaran"
              : summary.net_balance > 0
                ? "Surplus bulanan"
                : "Defisit (pengeluaran > pemasukan)"}
          </span>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Kategori Terbesar
          </span>
          <strong className="mt-1.5 block truncate text-xl font-extrabold tracking-tight text-slate-900">
            {topCategory ? topCategory.category : "-"}
          </strong>
          <span className="mt-1 block text-xs tabular-nums text-slate-500">
            {topCategory
              ? `${formatRupiah(topCategory.total)} (${topCategory.item_count} barang)`
              : "Belum ada transaksi"}
          </span>
        </article>
      </div>

      {/* AI Financial Insights (On-Demand) */}
      <div className="rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/60 to-white p-4 shadow-sm sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              AI Financial Insights
            </h3>
            <p className="mt-0.5 text-xs text-slate-600 sm:text-sm">
              Ringkasan naratif dan saran penghematan berbasis angka agregat{" "}
              {periodLabel}.
            </p>
          </div>

          <button
            type="button"
            disabled={isLoadingInsights}
            onClick={() => void handleAnalyzeInsights()}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60 sm:text-sm"
          >
            {isLoadingInsights ? (
              <>
                <span
                  className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
                  aria-hidden="true"
                />
                <span>Menganalisis...</span>
              </>
            ) : (
              <span>Analisis Keuangan Bulan Ini</span>
            )}
          </button>
        </div>

        {insightsError ? (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-medium text-red-800 sm:text-sm"
          >
            {insightsError}
          </div>
        ) : null}

        {insights ? (
          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
            {!insights.has_data ? (
              <p className="text-sm text-slate-600">{insights.summary_text}</p>
            ) : (
              <div className="space-y-3">
                <p className="text-sm leading-relaxed text-slate-800">
                  {insights.summary_text}
                </p>

                {insights.recommendations.length > 0 ? (
                  <div className="border-t border-slate-100 pt-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-700">
                      Saran Penghematan Praktis
                    </h4>
                    <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
                      {insights.recommendations.map((rec, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span
                            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600"
                            aria-hidden="true"
                          />
                          <span>{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        ) : !isLoadingInsights && !insightsError ? (
          <p className="mt-3 text-xs text-slate-500">
            Klik tombol di atas kapan saja untuk menghasilkan evaluasi kondisi
            keuangan bulan ini.
          </p>
        ) : null}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center gap-2.5 rounded-2xl border border-slate-200 bg-white py-14 text-sm text-slate-500 shadow-sm">
          <span
            className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
            aria-hidden="true"
          />
          <span>Menghitung ringkasan bulanan...</span>
        </div>
      ) : !hasData || !summary ? (
        <div className="rounded-2xl border border-slate-200 bg-white px-5 py-12 text-center shadow-sm">
          <p className="text-base font-bold text-slate-900">
            Belum ada pengeluaran tercatat pada {periodLabel}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Pilih periode bulan/tahun lainnya atau catat pengeluaran baru untuk
            melihat grafik dan rincian kategori.
          </p>
          <button
            type="button"
            onClick={onGoToEntry}
            className="mt-4 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800"
          >
            Catat Pengeluaran
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Category Breakdown: Donut Chart + Detailed List */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              Pengeluaran per Kategori
            </h3>
            <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
              Proporsi dan subtotal belanja pada {periodLabel} (diurutkan dari
              terbesar)
            </p>

            <div className="mt-4 grid grid-cols-1 items-center gap-6 lg:grid-cols-12">
              <div className="h-64 w-full min-w-0 lg:col-span-5">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={summary.category_breakdown}
                      dataKey="total"
                      nameKey="category"
                      cx="50%"
                      cy="50%"
                      innerRadius={56}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {summary.category_breakdown.map((entry) => (
                        <Cell
                          key={entry.category}
                          fill={CATEGORY_COLORS[entry.category].hex}
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<CategoryChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-3 lg:col-span-7">
                {summary.category_breakdown.map((entry) => {
                  const sharePct =
                    summary.total_expense > 0
                      ? (entry.total / summary.total_expense) * 100
                      : 0;
                  const barWidth =
                    summary.total_expense > 0
                      ? Math.min(100, Math.max(3, sharePct))
                      : 0;
                  const colorHex = CATEGORY_COLORS[entry.category].hex;

                  return (
                    <div
                      key={entry.category}
                      className="rounded-xl border border-slate-100 bg-slate-50/70 p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className="h-3 w-3 shrink-0 rounded-full"
                            style={{ backgroundColor: colorHex }}
                            aria-hidden="true"
                          />
                          <span className="text-sm font-semibold text-slate-900">
                            {entry.category}
                          </span>
                          <span className="text-xs text-slate-500">
                            ({entry.item_count} barang)
                          </span>
                        </div>

                        <div className="text-right tabular-nums">
                          <span className="text-sm font-bold text-slate-900">
                            {formatRupiah(entry.total)}
                          </span>
                          <span className="ml-2 text-xs font-semibold text-slate-500">
                            {sharePct.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${barWidth.toFixed(1)}%`,
                            backgroundColor: colorHex,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Daily Trend Bar Chart */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              Grafik Pengeluaran Harian
            </h3>
            <p className="mt-0.5 text-xs text-slate-500 sm:text-sm">
              Subtotal belanja per tanggal transaksi pada {periodLabel}
            </p>

            <div className="mt-4 h-72 w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={dailyChartData}
                  margin={{ top: 10, right: 12, left: 4, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="shortDate"
                    tick={{ fill: "#475569", fontSize: 12 }}
                    axisLine={{ stroke: "#cbd5e1" }}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v: number) => formatCompactRupiah(v)}
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={72}
                  />
                  <Tooltip content={<DailyChartTooltip />} />
                  <Bar
                    dataKey="total"
                    fill="#0f766e"
                    radius={[6, 6, 0, 0]}
                    maxBarSize={44}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Daily Breakdown Table */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
            <h3 className="text-base font-bold text-slate-900 sm:text-lg">
              Rincian Pengeluaran per Tanggal
            </h3>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs font-bold uppercase tracking-wider text-slate-500">
                    <th className="px-3 py-3">Tanggal Transaksi</th>
                    <th className="px-3 py-3 text-right">Jumlah Barang</th>
                    <th className="px-3 py-3 text-right">Subtotal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {summary.daily_breakdown.map((entry) => (
                    <tr key={entry.date} className="hover:bg-slate-50/70">
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-900">
                          {formatDateHuman(entry.date)}
                        </div>
                        <div className="text-xs text-slate-400">
                          {entry.date}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right text-slate-600">
                        {entry.item_count} barang
                      </td>
                      <td className="px-3 py-3 text-right font-bold tabular-nums text-slate-900">
                        {formatRupiah(entry.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
