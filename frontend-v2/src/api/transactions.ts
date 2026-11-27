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
import { requestJson } from "./client";

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

export function triggerCsvExportDownload(
  filters: TransactionListFilters = {},
): void {
  const exportUrl = buildExportTransactionsUrl(filters);
  const link = document.createElement("a");
  link.href = exportUrl;
  link.download = "";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function getTransactionReceiptUrl(transactionId: number): string {
  return `/api/transactions/${encodeURIComponent(transactionId)}/receipt`;
}
