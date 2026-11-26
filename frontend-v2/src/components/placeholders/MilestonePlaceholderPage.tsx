interface MilestonePlaceholderPageProps {
  title: string;
  description: string;
  plannedFeatures: readonly string[];
  onGoToEntry: () => void;
}

export function MilestonePlaceholderPage({
  title,
  description,
  plannedFeatures,
  onGoToEntry,
}: MilestonePlaceholderPageProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm sm:p-10">
      <span className="inline-flex items-center rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
        Segera Hadir di M2.2 (v1.5b)
      </span>

      <h2 className="mt-3 text-xl font-bold tracking-tight text-slate-900">
        {title}
      </h2>
      <p className="mx-auto mt-1.5 max-w-lg text-sm text-slate-600">
        {description}
      </p>

      <ul className="mx-auto mt-5 max-w-md space-y-1.5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3.5 text-left text-xs text-slate-700 sm:text-sm">
        {plannedFeatures.map((feat) => (
          <li key={feat} className="flex items-start gap-2">
            <span className="mt-0.5 text-brand-700" aria-hidden="true">
              •
            </span>
            <span>{feat}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6">
        <button
          type="button"
          onClick={onGoToEntry}
          className="inline-flex items-center justify-center rounded-lg bg-brand-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-800"
        >
          Kembali ke Catat Pengeluaran
        </button>
      </div>
    </section>
  );
}
