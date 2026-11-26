import { useState } from "react";
import { ManualEntryPanel } from "../components/entry/ManualEntryPanel";
import { ReceiptScanPanel } from "../components/entry/ReceiptScanPanel";

type EntryMode = "scan" | "manual";

interface ExpenseEntryPageProps {
  onSavedSuccess: (message: string) => void;
}

export function ExpenseEntryPage({ onSavedSuccess }: ExpenseEntryPageProps) {
  const [entryMode, setEntryMode] = useState<EntryMode>("scan");

  return (
    <section aria-label="Catat Pengeluaran">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            Catat Pengeluaran Baru
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Unggah foto struk belanja untuk diekstrak AI atau catat pengeluaran manual tanpa struk.
          </p>
        </div>

        <div
          className="grid grid-cols-2 gap-1 rounded-xl border border-slate-300 bg-white p-1 shadow-sm sm:inline-flex"
          role="group"
          aria-label="Mode Pencatatan Pengeluaran"
        >
          <button
            type="button"
            aria-pressed={entryMode === "scan"}
            onClick={() => setEntryMode("scan")}
            className={`rounded-lg px-3.5 py-2 text-xs font-semibold transition sm:text-sm ${
              entryMode === "scan"
                ? "bg-brand-700 text-white shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Scan Struk (AI)
          </button>
          <button
            type="button"
            aria-pressed={entryMode === "manual"}
            onClick={() => setEntryMode("manual")}
            className={`rounded-lg px-3.5 py-2 text-xs font-semibold transition sm:text-sm ${
              entryMode === "manual"
                ? "bg-brand-700 text-white shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Input Manual
          </button>
        </div>
      </div>

      {entryMode === "scan" ? (
        <ReceiptScanPanel onSavedSuccess={onSavedSuccess} />
      ) : (
        <ManualEntryPanel onSavedSuccess={onSavedSuccess} />
      )}
    </section>
  );
}
