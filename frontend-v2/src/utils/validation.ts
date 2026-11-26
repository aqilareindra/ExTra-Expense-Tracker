import { isValidCategory } from "../constants/categories";
import type { EditableItemDraft, TransactionItemCreate } from "../types/api";
import {
  isValidIsoCalendarDate,
  parseStrictNonNegativeInt,
} from "./formatters";

export interface EntryValidationResult {
  isValid: boolean;
  dateError: string | null;
  bannerError: string | null;
  validatedDrafts: EditableItemDraft[];
  payloadItems: TransactionItemCreate[];
}

export function validateEntryForm(
  dateValue: string,
  drafts: EditableItemDraft[],
): EntryValidationResult {
  const trimmedDate = dateValue.trim();
  let dateError: string | null = null;
  let firstBannerError: string | null = null;

  if (!isValidIsoCalendarDate(trimmedDate)) {
    dateError = "Tanggal transaksi wajib diisi dengan tanggal kalender yang valid.";
    firstBannerError = dateError;
  }

  if (drafts.length === 0) {
    const emptyMsg = "Daftar barang minimal harus berisi 1 item.";
    return {
      isValid: false,
      dateError,
      bannerError: firstBannerError ?? emptyMsg,
      validatedDrafts: [],
      payloadItems: [],
    };
  }

  const payloadItems: TransactionItemCreate[] = [];
  let hasRowError = false;

  const validatedDrafts = drafts.map((row, idx) => {
    const trimmedName = row.name.trim();
    const parsedPrice = parseStrictNonNegativeInt(row.price);
    const validCategory = isValidCategory(row.category);

    let nameError: string | undefined;
    let categoryError: string | undefined;
    let priceError: string | undefined;

    if (!trimmedName) {
      nameError = "Nama barang wajib diisi.";
      hasRowError = true;
      if (!firstBannerError) {
        firstBannerError = `Baris #${idx + 1}: Nama barang tidak boleh kosong.`;
      }
    }

    if (!validCategory) {
      categoryError = "Pilih kategori resmi.";
      hasRowError = true;
      if (!firstBannerError) {
        firstBannerError = `Baris #${idx + 1}: Kategori pengeluaran tidak valid.`;
      }
    }

    if (parsedPrice === null) {
      priceError = "Bilangan bulat >= 0.";
      hasRowError = true;
      if (!firstBannerError) {
        firstBannerError = `Baris #${idx + 1}: Harga harus berupa bilangan bulat minimal 0.`;
      }
    }

    if (!nameError && validCategory && parsedPrice !== null) {
      payloadItems.push({
        name: trimmedName,
        price: parsedPrice,
        category: row.category,
      });
    }

    return {
      ...row,
      nameError,
      categoryError,
      priceError,
    };
  });

  const isValid = dateError === null && !hasRowError && payloadItems.length > 0;
  return {
    isValid,
    dateError,
    bannerError: isValid ? null : firstBannerError,
    validatedDrafts,
    payloadItems,
  };
}
