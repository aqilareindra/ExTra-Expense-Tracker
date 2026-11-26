import {
  EXPENSE_CATEGORIES,
  type ExpenseCategory,
} from "../../constants/categories";
import type { EditableItemDraft } from "../../types/api";
import {
  formatRupiah,
  parseStrictNonNegativeInt,
} from "../../utils/formatters";

interface EditableItemsListProps {
  items: EditableItemDraft[];
  disabled?: boolean;
  addLabel?: string;
  estimateLabel?: string;
  onUpdateRow: (
    localId: string,
    patch: Partial<
      Pick<EditableItemDraft, "name" | "category" | "price">
    >,
  ) => void;
  onRemoveRow: (localId: string) => void;
  onAddRow: () => void;
}

export function EditableItemsList({
  items,
  disabled = false,
  addLabel = "+ Tambah Barang",
  estimateLabel = "Estimasi Total Preview",
  onUpdateRow,
  onRemoveRow,
  onAddRow,
}: EditableItemsListProps) {
  const estimatedTotal = items.reduce((acc, row) => {
    const parsed = parseStrictNonNegativeInt(row.price);
    return acc + (parsed ?? 0);
  }, 0);

  return (
    <div className="space-y-4">
      {/* Desktop Table View */}
      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 md:block">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-xs font-bold uppercase tracking-wider text-slate-500">
              <th className="w-12 px-3 py-3">#</th>
              <th className="px-3 py-3">
                Nama Barang <span className="text-red-600">*</span>
              </th>
              <th className="w-52 px-3 py-3">
                Kategori <span className="text-red-600">*</span>
              </th>
              <th className="w-40 px-3 py-3">
                Harga (Rp) <span className="text-red-600">*</span>
              </th>
              <th className="w-24 px-3 py-3 text-center">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {items.map((row, idx) => (
              <tr key={row.localId} className="align-top hover:bg-slate-50/60">
                <td className="px-3 py-3.5 text-slate-500">{idx + 1}</td>
                <td className="px-3 py-2.5">
                  <input
                    type="text"
                    value={row.name}
                    maxLength={200}
                    disabled={disabled}
                    placeholder="Contoh: Susu UHT 1L"
                    onChange={(e) =>
                      onUpdateRow(row.localId, { name: e.target.value })
                    }
                    className={`w-full rounded-lg border px-3 py-2 text-sm text-slate-900 transition focus:outline-none focus:ring-2 ${
                      row.nameError
                        ? "border-red-500 bg-red-50 focus:ring-red-200"
                        : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                    }`}
                  />
                  {row.nameError ? (
                    <p className="mt-1 text-xs font-medium text-red-600">
                      {row.nameError}
                    </p>
                  ) : null}
                </td>
                <td className="px-3 py-2.5">
                  <select
                    value={row.category}
                    disabled={disabled}
                    aria-label={`Kategori baris ${idx + 1}`}
                    onChange={(e) =>
                      onUpdateRow(row.localId, {
                        category: e.target.value as ExpenseCategory,
                      })
                    }
                    className={`w-full rounded-lg border px-2.5 py-2 text-sm text-slate-900 transition focus:outline-none focus:ring-2 ${
                      row.categoryError
                        ? "border-red-500 bg-red-50 focus:ring-red-200"
                        : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                    }`}
                  >
                    {EXPENSE_CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="number"
                    min={0}
                    step={1}
                    inputMode="numeric"
                    value={row.price}
                    disabled={disabled}
                    placeholder="0"
                    onChange={(e) =>
                      onUpdateRow(row.localId, { price: e.target.value })
                    }
                    className={`w-full rounded-lg border px-3 py-2 text-right text-sm tabular-nums text-slate-900 transition focus:outline-none focus:ring-2 ${
                      row.priceError
                        ? "border-red-500 bg-red-50 focus:ring-red-200"
                        : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                    }`}
                  />
                  {row.priceError ? (
                    <p className="mt-1 text-xs font-medium text-red-600">
                      {row.priceError}
                    </p>
                  ) : null}
                </td>
                <td className="px-3 py-2.5 text-center">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onRemoveRow(row.localId)}
                    className="rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                  >
                    Hapus
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Stack View (360px+) */}
      <div className="flex flex-col gap-3 md:hidden">
        {items.map((row, idx) => (
          <div
            key={row.localId}
            className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 shadow-sm"
          >
            <div className="mb-2.5 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wide text-slate-500">
                Barang #{idx + 1}
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onRemoveRow(row.localId)}
                className="rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50"
              >
                Hapus
              </button>
            </div>

            <div className="space-y-2.5">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Nama Barang <span className="text-red-600">*</span>
                </label>
                <input
                  type="text"
                  value={row.name}
                  maxLength={200}
                  disabled={disabled}
                  placeholder="Contoh: Susu UHT 1L"
                  onChange={(e) =>
                    onUpdateRow(row.localId, { name: e.target.value })
                  }
                  className={`w-full rounded-lg border px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 ${
                    row.nameError
                      ? "border-red-500 bg-red-50 focus:ring-red-200"
                      : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                  }`}
                />
                {row.nameError ? (
                  <p className="mt-1 text-xs font-medium text-red-600">
                    {row.nameError}
                  </p>
                ) : null}
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Kategori <span className="text-red-600">*</span>
                  </label>
                  <select
                    value={row.category}
                    disabled={disabled}
                    onChange={(e) =>
                      onUpdateRow(row.localId, {
                        category: e.target.value as ExpenseCategory,
                      })
                    }
                    className={`w-full rounded-lg border px-2.5 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 ${
                      row.categoryError
                        ? "border-red-500 bg-red-50 focus:ring-red-200"
                        : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                    }`}
                  >
                    {EXPENSE_CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Harga (Rp) <span className="text-red-600">*</span>
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    inputMode="numeric"
                    value={row.price}
                    disabled={disabled}
                    placeholder="0"
                    onChange={(e) =>
                      onUpdateRow(row.localId, { price: e.target.value })
                    }
                    className={`w-full rounded-lg border px-3 py-2 text-sm tabular-nums text-slate-900 focus:outline-none focus:ring-2 ${
                      row.priceError
                        ? "border-red-500 bg-red-50 focus:ring-red-200"
                        : "border-slate-300 bg-white focus:border-brand-700 focus:ring-brand-200"
                    }`}
                  />
                  {row.priceError ? (
                    <p className="mt-1 text-xs font-medium text-red-600">
                      {row.priceError}
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty Rows Fallback */}
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-center text-sm text-slate-500">
          Belum ada baris barang. Tekan tombol <strong>{addLabel}</strong> untuk menambahkan.
        </div>
      ) : null}

      {/* Toolbar & Estimate */}
      <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          disabled={disabled}
          onClick={onAddRow}
          className="inline-flex items-center justify-center rounded-lg border border-brand-200 bg-brand-50 px-3.5 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-100 disabled:opacity-50"
        >
          {addLabel}
        </button>

        <div className="text-sm text-slate-600 tabular-nums">
          {estimateLabel}:{" "}
          <strong className="text-base font-bold text-slate-900">
            {formatRupiah(estimatedTotal)}
          </strong>
        </div>
      </div>
    </div>
  );
}
