import { normalizeCategory } from "../constants/categories";
import type {
  ItemDeleteResponse,
  ItemUpdateRequest,
  ItemUpdateResponse,
  TransactionCreateRequest,
  TransactionCreateResponse,
  TransactionDeleteResponse,
  TransactionItemRecord,
  TransactionListFilters,
  TransactionListResponse,
} from "../types/api";
import { ApiClientError, notifyUnauthorized, requestJson } from "./client";

function normalizeRecord(item: TransactionItemRecord): TransactionItemRecord {
  return {
    ...item,
    category: normalizeCategory(item.category),
    has_receipt: Boolean(item.has_receipt),
  };
}

function buildFilterQueryString(filters: TransactionListFilters = {}): string {
  const params = new URLSearchParams();
  if (
    filters.month !== undefined &&
    filters.month !== "" &&
    Number.isFinite(Number(filters.month))
  ) {
    params.set("month", String(filters.month));
  }
  if (
    filters.year !== undefined &&
    filters.year !== "" &&
    Number.isFinite(Number(filters.year))
  ) {
    params.set("year", String(filters.year));
  }
  if (filters.category !== undefined && String(filters.category).trim() !== "") {
    params.set("category", String(filters.category).trim());
  }
  if (filters.search !== undefined && filters.search.trim() !== "") {
    params.set("search", filters.search.trim());
  }
  return params.toString();
}

export async function createTransaction(
  payload: TransactionCreateRequest,
): Promise<TransactionCreateResponse> {
  const response = await requestJson<TransactionCreateResponse>(
    "/api/transactions",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return {
    ...response,
    data: {
      ...response.data,
      has_receipt: Boolean(response.data.has_receipt),
      items: Array.isArray(response.data.items)
        ? response.data.items.map(normalizeRecord)
        : [],
    },
  };
}

export async function getTransactions(
  filters: TransactionListFilters = {},
): Promise<TransactionListResponse> {
  const qs = buildFilterQueryString(filters);
  const url = qs ? `/api/transactions?${qs}` : "/api/transactions";
  const response = await requestJson<TransactionListResponse>(url, {
    method: "GET",
  });
  return {
    ...response,
    data: Array.isArray(response.data) ? response.data.map(normalizeRecord) : [],
  };
}

export async function updateItem(
  itemId: number,
  payload: ItemUpdateRequest,
): Promise<ItemUpdateResponse> {
  const response = await requestJson<ItemUpdateResponse>(
    `/api/items/${encodeURIComponent(itemId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return {
    ...response,
    data: normalizeRecord(response.data),
  };
}

export async function deleteItem(itemId: number): Promise<ItemDeleteResponse> {
  return requestJson<ItemDeleteResponse>(
    `/api/items/${encodeURIComponent(itemId)}`,
    {
      method: "DELETE",
    },
  );
}

export async function deleteTransaction(
  transactionId: number,
): Promise<TransactionDeleteResponse> {
  return requestJson<TransactionDeleteResponse>(
    `/api/transactions/${encodeURIComponent(transactionId)}`,
    {
      method: "DELETE",
    },
  );
}

export function buildExportTransactionsUrl(
  filters: TransactionListFilters = {},
): string {
  const qs = buildFilterQueryString(filters);
  return qs ? `/api/transactions/export?${qs}` : "/api/transactions/export";
}

function extractFilenameFromHeader(
  contentDisposition: string | null,
): string {
  if (!contentDisposition) {
    return "extra-pengeluaran.csv";
  }
  const match = /filename="?([^";\n]+)"?/i.exec(contentDisposition);
  return match && match[1] ? match[1].trim() : "extra-pengeluaran.csv";
}

export async function triggerCsvExportDownload(
  filters: TransactionListFilters = {},
): Promise<void> {
  const exportUrl = buildExportTransactionsUrl(filters);
  let response: Response;
  try {
    response = await fetch(exportUrl, {
      method: "GET",
      credentials: "include",
    });
  } catch {
    throw new ApiClientError(
      "Tidak dapat terhubung ke server ExTra saat mengunduh CSV.",
      0,
      "NETWORK_ERROR",
      [],
    );
  }

  if (response.status === 401) {
    notifyUnauthorized();
    throw new ApiClientError(
      "Sesi login telah berakhir. Silakan masuk kembali.",
      401,
      "UNAUTHORIZED",
      [],
    );
  }

  if (!response.ok) {
    throw new ApiClientError(
      `Gagal mengunduh laporan CSV (HTTP ${response.status}).`,
      response.status,
      `HTTP_${response.status}`,
      [],
    );
  }

  const blob = await response.blob();
  const filename = extractFilenameFromHeader(
    response.headers.get("content-disposition"),
  );
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 1000);
}

export function getTransactionReceiptUrl(transactionId: number): string {
  return `/api/transactions/${encodeURIComponent(transactionId)}/receipt`;
}
