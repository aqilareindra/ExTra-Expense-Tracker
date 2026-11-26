import { useEffect, useState } from "react";
import { ToastBanner } from "./components/common/ToastBanner";
import { AppHeader, type AppTab } from "./components/layout/AppHeader";
import { MilestonePlaceholderPage } from "./components/placeholders/MilestonePlaceholderPage";
import { ExpenseEntryPage } from "./pages/ExpenseEntryPage";

export function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("entry");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => {
      setToastMessage(null);
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <AppHeader activeTab={activeTab} onSelectTab={setActiveTab} />

      <main className="mx-auto max-w-5xl px-4 pb-14 pt-6">
        {toastMessage ? (
          <ToastBanner
            message={toastMessage}
            actionLabel={activeTab === "entry" ? "Cek Tab Riwayat" : undefined}
            onAction={
              activeTab === "entry" ? () => setActiveTab("history") : undefined
            }
            onDismiss={() => setToastMessage(null)}
          />
        ) : null}

        {activeTab === "entry" ? (
          <ExpenseEntryPage onSavedSuccess={(msg) => setToastMessage(msg)} />
        ) : null}

        {activeTab === "history" ? (
          <MilestonePlaceholderPage
            title="Riwayat Transaksi"
            description="Halaman riwayat modern di React sedang disiapkan untuk sub-milestone M2.2 (v1.5b). Data yang baru Anda simpan sudah tersimpan aman di backend."
            plannedFeatures={[
              "Pencarian barang, filter bulan/tahun, dan filter 7 kategori resmi.",
              "Edit item, hapus item/transaksi, serta lihat arsip foto struk.",
              "Ekspor laporan pengeluaran bulanan ke format CSV (UTF-8 BOM).",
            ]}
            onGoToEntry={() => setActiveTab("entry")}
          />
        ) : null}

        {activeTab === "summary" ? (
          <MilestonePlaceholderPage
            title="Ringkasan Bulanan"
            description="Dashboard ringkasan bulanan dan grafik modern sedang disiapkan untuk sub-milestone M2.2 (v1.5b)."
            plannedFeatures={[
              "Total pengeluaran bulanan dan jumlah barang tercatat deterministik.",
              "Rincian pengeluaran per kategori dan grafik tren harian interaktif.",
              "Cutover production build frontend-v2 ke server FastAPI.",
            ]}
            onGoToEntry={() => setActiveTab("entry")}
          />
        ) : null}
      </main>
    </div>
  );
}

export default App;
