import { useState, type FormEvent } from "react";
import { ApiClientError } from "../api/client";
import { useAuth } from "../context/AuthContext";

type AuthMode = "login" | "register";

export function AuthPage() {
  const { login, register, sessionNotice, clearSessionNotice } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setErrorMessage(null);
    clearSessionNotice();
    setPassword("");
    setConfirmPassword("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setErrorMessage(null);
    clearSessionNotice();

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setErrorMessage("Masukkan alamat email yang valid.");
      return;
    }

    if (!password) {
      setErrorMessage("Password wajib diisi.");
      return;
    }

    if (mode === "register") {
      if (password.length < 8) {
        setErrorMessage("Password minimal terdiri dari 8 karakter.");
        return;
      }
      if (password !== confirmPassword) {
        setErrorMessage("Konfirmasi password tidak cocok.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      if (mode === "login") {
        await login({ email: trimmedEmail, password });
      } else {
        await register({ email: trimmedEmail, password });
      }
    } catch (err) {
      const msg =
        err instanceof ApiClientError || err instanceof Error
          ? err.message
          : "Terjadi kesalahan saat memproses autentikasi.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col justify-center bg-slate-50 px-4 py-10">
      <div className="mx-auto w-full max-w-md">
        {/* Brand Header */}
        <div className="mb-6 flex flex-col items-center text-center">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-700 to-brand-600 text-lg font-bold tracking-tight text-white shadow-md"
            aria-hidden="true"
          >
            Ex
          </div>
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900">
            ExTra
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Pencatat Pengeluaran Struk Belanja Berbasis AI
          </p>
        </div>

        {/* Auth Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          {/* Mode Toggle */}
          <div
            className="mb-5 grid grid-cols-2 gap-1 rounded-xl border border-slate-200 bg-slate-100 p-1"
            role="tablist"
            aria-label="Pilih mode autentikasi"
          >
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              onClick={() => switchMode("login")}
              className={`rounded-lg py-2 text-sm font-semibold transition ${
                mode === "login"
                  ? "bg-white text-brand-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Masuk
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              onClick={() => switchMode("register")}
              className={`rounded-lg py-2 text-sm font-semibold transition ${
                mode === "register"
                  ? "bg-white text-brand-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Daftar Akun
            </button>
          </div>

          <h2 className="text-lg font-bold text-slate-900">
            {mode === "login"
              ? "Masuk ke Akun Anda"
              : "Buat Akun ExTra Baru"}
          </h2>
          <p className="mt-1 text-xs text-slate-500 sm:text-sm">
            {mode === "login"
              ? "Catatan pengeluaran dan arsip foto struk Anda tersimpan aman per akun."
              : "Gunakan alamat email aktif dan password minimal 8 karakter."}
          </p>

          {sessionNotice ? (
            <div
              role="status"
              className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs font-medium text-amber-800 sm:text-sm"
            >
              {sessionNotice}
            </div>
          ) : null}

          {errorMessage ? (
            <div
              role="alert"
              className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs font-medium text-red-800 sm:text-sm"
            >
              {errorMessage}
            </div>
          ) : null}

          <form onSubmit={(e) => void handleSubmit(e)} className="mt-5 space-y-4" noValidate>
            <div>
              <label
                htmlFor="auth-email"
                className="mb-1 block text-xs font-semibold text-slate-700 sm:text-sm"
              >
                Email
              </label>
              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nama@contoh.com"
                required
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <label
                  htmlFor="auth-password"
                  className="text-xs font-semibold text-slate-700 sm:text-sm"
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800"
                >
                  {showPassword ? "Sembunyikan" : "Tampilkan"}
                </button>
              </div>
              <input
                id="auth-password"
                type={showPassword ? "text" : "password"}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={
                  mode === "register"
                    ? "Minimal 8 karakter"
                    : "Masukkan password"
                }
                required
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>

            {mode === "register" ? (
              <div>
                <label
                  htmlFor="auth-confirm-password"
                  className="mb-1 block text-xs font-semibold text-slate-700 sm:text-sm"
                >
                  Konfirmasi Password
                </label>
                <input
                  id="auth-confirm-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Ulangi password Anda"
                  required
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
                />
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <span
                    className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
                    aria-hidden="true"
                  />
                  <span>
                    {mode === "login" ? "Memproses..." : "Mendaftarkan..."}
                  </span>
                </>
              ) : mode === "login" ? (
                "Masuk"
              ) : (
                "Daftar & Masuk"
              )}
            </button>
          </form>

          <p className="mt-5 text-center text-xs text-slate-500">
            {mode === "login" ? (
              <>
                Belum punya akun?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="font-semibold text-brand-700 hover:underline"
                >
                  Daftar di sini
                </button>
              </>
            ) : (
              <>
                Sudah punya akun?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("login")}
                  className="font-semibold text-brand-700 hover:underline"
                >
                  Masuk sekarang
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
