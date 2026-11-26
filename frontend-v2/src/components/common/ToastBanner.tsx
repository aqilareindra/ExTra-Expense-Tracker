interface ToastBannerProps {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  onDismiss: () => void;
}

export function ToastBanner({
  message,
  actionLabel,
  onAction,
  onDismiss,
}: ToastBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-5 flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900 shadow-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-2.5 sm:items-center">
        <span
          className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white sm:mt-0"
          aria-hidden="true"
        >
          ✓
        </span>
        <span>{message}</span>
      </div>

      <div className="flex items-center justify-end gap-2">
        {actionLabel && onAction ? (
          <button
            type="button"
            onClick={onAction}
            className="rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 transition hover:bg-emerald-100"
          >
            {actionLabel}
          </button>
        ) : null}
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Tutup notifikasi"
          className="rounded-lg px-2 py-1 text-xs font-semibold text-emerald-700 transition hover:bg-emerald-100"
        >
          Tutup
        </button>
      </div>
    </div>
  );
}
