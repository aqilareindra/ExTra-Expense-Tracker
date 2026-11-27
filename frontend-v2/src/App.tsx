import { useEffect, useState } from "react";
import { ToastBanner } from "./components/common/ToastBanner";
import { AppHeader, type AppTab } from "./components/layout/AppHeader";
import { ExpenseEntryPage } from "./pages/ExpenseEntryPage";
import { MonthlySummaryPage } from "./pages/MonthlySummaryPage";
import { TransactionHistoryPage } from "./pages/TransactionHistoryPage";

export function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("entry");
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [dataVersion, setDataVersion] = useState(0);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => {
      setToastMessage(null);
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  const handleDataChanged = (msg: string) => {
    setDataVersion((prev) => prev + 1);
    setToastMessage(msg);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <AppHeader activeTab={activeTab} onSelectTab={setActiveTab} />

      <main className="mx-auto max-w-5xl px-4 pb-14 pt-6">
        {toastMessage ? (
          <ToastBanner
            message={toastMessage}
            actionLabel={activeTab === "entry" ? "Lihat Riwayat" : undefined}
            onAction={
              activeTab === "entry" ? () => setActiveTab("history") : undefined
            }
            onDismiss={() => setToastMessage(null)}
          />
        ) : null}

        {activeTab === "entry" ? (
          <ExpenseEntryPage onSavedSuccess={handleDataChanged} />
        ) : null}

        {activeTab === "history" ? (
          <TransactionHistoryPage
            refreshKey={dataVersion}
            onDataMutated={handleDataChanged}
            onGoToEntry={() => setActiveTab("entry")}
          />
        ) : null}

        {activeTab === "summary" ? (
          <MonthlySummaryPage
            refreshKey={dataVersion}
            onGoToEntry={() => setActiveTab("entry")}
          />
        ) : null}
      </main>
    </div>
  );
}

export default App;
