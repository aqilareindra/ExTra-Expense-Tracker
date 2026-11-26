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
