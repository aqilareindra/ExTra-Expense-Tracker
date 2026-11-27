export const EXPENSE_CATEGORIES = [
  "Makanan & Minuman",
  "Kebutuhan Pokok",
  "Transportasi",
  "Kesehatan & Perawatan",
  "Tagihan & Utilitas",
  "Hiburan & Belanja",
  "Lainnya",
] as const;

export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number];

export const DEFAULT_CATEGORY: ExpenseCategory = "Lainnya";

export const CATEGORY_COLORS: Record<
  ExpenseCategory,
  { hex: string; badgeClass: string }
> = {
  "Makanan & Minuman": {
    hex: "#0f766e",
    badgeClass: "border-teal-200 bg-teal-50 text-teal-800",
  },
  "Kebutuhan Pokok": {
    hex: "#0284c7",
    badgeClass: "border-sky-200 bg-sky-50 text-sky-800",
  },
  Transportasi: {
    hex: "#d97706",
    badgeClass: "border-amber-200 bg-amber-50 text-amber-800",
  },
  "Kesehatan & Perawatan": {
    hex: "#e11d48",
    badgeClass: "border-rose-200 bg-rose-50 text-rose-800",
  },
  "Tagihan & Utilitas": {
    hex: "#7c3aed",
    badgeClass: "border-violet-200 bg-violet-50 text-violet-800",
  },
  "Hiburan & Belanja": {
    hex: "#ea580c",
    badgeClass: "border-orange-200 bg-orange-50 text-orange-800",
  },
  Lainnya: {
    hex: "#475569",
    badgeClass: "border-slate-200 bg-slate-100 text-slate-700",
  },
};

export function isValidCategory(value: unknown): value is ExpenseCategory {
  if (typeof value !== "string") {
    return false;
  }
  const trimmed = value.trim();
  return (EXPENSE_CATEGORIES as readonly string[]).includes(trimmed);
}

export function normalizeCategory(value: unknown): ExpenseCategory {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if ((EXPENSE_CATEGORIES as readonly string[]).includes(trimmed)) {
      return trimmed as ExpenseCategory;
    }
  }
  return DEFAULT_CATEGORY;
}
