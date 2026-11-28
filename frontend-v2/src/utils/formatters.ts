import { DEFAULT_CATEGORY, type ExpenseCategory } from "../constants/categories";
import type { EditableItemDraft } from "../types/api";

export const MONTH_NAMES_ID = [
  "",
  "Januari",
  "Februari",
  "Maret",
  "April",
  "Mei",
  "Juni",
  "Juli",
  "Agustus",
  "September",
  "Oktober",
  "November",
  "Desember",
] as const;

const MONTH_SHORT_ID = [
  "",
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "Mei",
  "Jun",
  "Jul",
  "Agu",
  "Sep",
  "Okt",
  "Nov",
  "Des",
] as const;

const idrFormatter = new Intl.NumberFormat("id-ID", {
  maximumFractionDigits: 0,
});

export function getMonthName(monthNumber: number): string {
  return MONTH_NAMES_ID[monthNumber] ?? "";
}

export function formatRupiah(value: number): string {
  if (!Number.isFinite(value)) {
    return "Rp 0";
  }
  const truncated = Math.trunc(value);
  if (truncated < 0) {
    return `-Rp ${idrFormatter.format(Math.abs(truncated))}`;
  }
  return `Rp ${idrFormatter.format(truncated)}`;
}

export function formatCompactRupiah(value: number): string {
  const num = Number(value) || 0;
  if (num >= 1_000_000) {
    const jt = num / 1_000_000;
    const formatted = Number.isInteger(jt)
      ? String(jt)
      : jt.toFixed(1).replace(".", ",");
    return `Rp ${formatted}jt`;
  }
  if (num >= 1_000) {
    return `Rp ${Math.round(num / 1_000)}rb`;
  }
  return `Rp ${Math.trunc(num)}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatDateHuman(isoDate: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return isoDate || "-";
  }
  const [yearStr, monthStr, dayStr] = isoDate.split("-");
  const monthIdx = Number(monthStr);
  const dayNum = Number(dayStr);
  return `${dayNum} ${MONTH_SHORT_ID[monthIdx] ?? monthStr} ${yearStr}`;
}

export function getTodayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function isValidIsoCalendarDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const [y, m, d] = value.split("-").map(Number);
  const candidate = new Date(Date.UTC(y, m - 1, d));
  return (
    candidate.getUTCFullYear() === y &&
    candidate.getUTCMonth() === m - 1 &&
    candidate.getUTCDate() === d
  );
}

export function parseStrictNonNegativeInt(rawValue: string): number | null {
  const trimmed = rawValue.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    return null;
  }
  return parsed;
}

let draftCounter = 0;

export function createEmptyDraftRow(
  category: ExpenseCategory = DEFAULT_CATEGORY,
): EditableItemDraft {
  draftCounter += 1;
  return {
    localId: `draft-${Date.now()}-${draftCounter}`,
    name: "",
    category,
    price: "",
  };
}
