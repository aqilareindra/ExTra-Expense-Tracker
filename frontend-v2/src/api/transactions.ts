import type {
  TransactionCreateRequest,
  TransactionCreateResponse,
} from "../types/api";
import { requestJson } from "./client";

export async function createTransaction(
  payload: TransactionCreateRequest,
): Promise<TransactionCreateResponse> {
  return requestJson<TransactionCreateResponse>("/api/transactions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
