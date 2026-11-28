export type AppTab = "entry" | "history" | "summary";

interface AppHeaderProps {
  activeTab: AppTab;
  onSelectTab: (tab: AppTab) => void;
  userEmail: string;
  onLogout: () => void;
  isLoggingOut?: boolean;
}

const NAV_ITEMS: readonly { id: AppTab; label: string; shortLabel: string }[] = [
  { id: "entry", label: "Catat Pengeluaran", shortLabel: "Catat" },
  { id: "history", label: "Riwayat Transaksi", shortLabel: "Riwayat" },
  { id: "summary", label: "Ringkasan Bulanan", shortLabel: "Ringkasan" },
];

export function AppHeader({
  activeTab,
  onSelectTab,
  userEmail,
  onLogout,
  isLoggingOut = false,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-3.5">
        {/* Top Row: Brand & Session Info */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
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

          <div className="flex shrink-0 items-center gap-2">
            <span
              title={userEmail}
              className="hidden max-w-[180px] truncate rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-700 sm:inline-block"
            >
              {userEmail}
            </span>
            <button
              type="button"
              onClick={onLogout}
              disabled={isLoggingOut}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoggingOut ? "Keluar..." : "Keluar"}
            </button>
          </div>
        </div>

        {/* Mobile email line + Navigation tabs */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="truncate text-xs text-slate-500 sm:hidden">
            Masuk sebagai <strong className="text-slate-700">{userEmail}</strong>
          </p>

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
      </div>
    </header>
  );
}
