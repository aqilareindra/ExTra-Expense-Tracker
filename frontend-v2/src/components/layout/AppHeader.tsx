export type AppTab = "entry" | "history" | "summary";

interface AppHeaderProps {
  activeTab: AppTab;
  onSelectTab: (tab: AppTab) => void;
}

const NAV_ITEMS: readonly { id: AppTab; label: string; shortLabel: string }[] = [
  { id: "entry", label: "Catat Pengeluaran", shortLabel: "Catat" },
  { id: "history", label: "Riwayat Transaksi", shortLabel: "Riwayat" },
  { id: "summary", label: "Ringkasan Bulanan", shortLabel: "Ringkasan" },
];

export function AppHeader({ activeTab, onSelectTab }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-700 to-brand-600 text-base font-bold tracking-tight text-white shadow-sm"
            aria-hidden="true"
          >
            Ex
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold leading-tight tracking-tight text-slate-900">
              ExTra
            </h1>
            <p className="truncate text-xs text-slate-500">
              Pencatat Pengeluaran Struk Belanja Berbasis AI
            </p>
          </div>
        </div>

        <nav
          className="grid grid-cols-3 gap-1 rounded-xl border border-slate-200 bg-slate-100 p-1 sm:flex sm:w-auto"
          role="tablist"
          aria-label="Navigasi Utama"
        >
          {NAV_ITEMS.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onSelectTab(item.id)}
                className={`rounded-lg px-2 py-2 text-center text-xs font-semibold transition sm:px-3.5 sm:text-sm ${
                  isActive
                    ? "bg-white text-brand-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <span className="sm:hidden">{item.shortLabel}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
