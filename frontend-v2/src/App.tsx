import { useEffect, useState } from "react";
import { ToastBanner } from "./components/common/ToastBanner";
import { AppHeader, type AppTab } from "./components/layout/AppHeader";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AuthPage } from "./pages/AuthPage";
import { ExpenseEntryPage } from "./pages/ExpenseEntryPage";
import { MonthlySummaryPage } from "./pages/MonthlySummaryPage";
import { TransactionHistoryPage } from "./pages/TransactionHistoryPage";

function AuthenticatedWorkspace() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<AppTab>("entry");
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => {
      setToastMessage(null);
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  if (!user) {
    return null;
  }

  const handleDataChanged = (msg: string) => {
    setDataVersion((prev) => prev + 1);
    setToastMessage(msg);
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <AppHeader
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        userEmail={user.email}
        onLogout={() => void handleLogout()}
        isLoggingOut={isLoggingOut}
      />

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

function AppContent() {
  const { user, isCheckingSession } = useAuth();

  if (isCheckingSession) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm font-medium text-slate-600 shadow-sm">
          <span
            className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700"
            aria-hidden="true"
          />
          <span>Memeriksa sesi ExTra...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return <AuthenticatedWorkspace key={user.id} />;
}

export function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
