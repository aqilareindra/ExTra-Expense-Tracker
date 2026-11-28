import { normalizeCategory } from "../constants/categories";
import type {
  BudgetDeleteResponse,
  BudgetListResponse,
  BudgetStatusItem,
  BudgetUpsertRequest,
  BudgetUpsertResponse,
  IncomeCreateRequest,
  IncomeDeleteResponse,
  IncomeListResponse,
  IncomeResponse,
  MonthlyInsightsResponse,
} from "../types/api";
import { requestJson } from "./client";

function normalizeBudgetItem(item: BudgetStatusItem): BudgetStatusItem {
  return {
    ...item,
    category: normalizeCategory(item.category),
  };
}

export async function createIncome(
  payload: IncomeCreateRequest,
): Promise<IncomeResponse> {
  return requestJson<IncomeResponse>("/api/incomes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getIncomes(
  month?: number,
  year?: number,
): Promise<IncomeListResponse> {
  const params = new URLSearchParams();
  if (month !== undefined) params.set("month", String(month));
  if (year !== undefined) params.set("year", String(year));
  const qs = params.toString();
  const url = qs ? `/api/incomes?${qs}` : "/api/incomes";
  return requestJson<IncomeListResponse>(url, { method: "GET" });
}

export async function deleteIncome(
  incomeId: number,
): Promise<IncomeDeleteResponse> {
  return requestJson<IncomeDeleteResponse>(
    `/api/incomes/${encodeURIComponent(incomeId)}`,
    { method: "DELETE" },
  );
}

export async function getBudgets(
  month: number,
  year: number,
): Promise<BudgetListResponse> {
  const params = new URLSearchParams({
    month: String(month),
    year: String(year),
  });
  const response = await requestJson<BudgetListResponse>(
    `/api/budgets?${params.toString()}`,
    { method: "GET" },
  );
  return {
    ...response,
    data: Array.isArray(response.data)
      ? response.data.map(normalizeBudgetItem)
      : [],
  };
}

export async function upsertBudget(
  payload: BudgetUpsertRequest,
): Promise<BudgetUpsertResponse> {
  const response = await requestJson<BudgetUpsertResponse>("/api/budgets", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return {
    ...response,
    data: normalizeBudgetItem(response.data),
  };
}

export async function deleteBudget(
  budgetId: number,
): Promise<BudgetDeleteResponse> {
  return requestJson<BudgetDeleteResponse>(
    `/api/budgets/${encodeURIComponent(budgetId)}`,
    { method: "DELETE" },
  );
}

export async function getMonthlyInsights(
  month: number,
  year: number,
): Promise<MonthlyInsightsResponse> {
  const params = new URLSearchParams({
    month: String(month),
    year: String(year),
  });
  const response = await requestJson<MonthlyInsightsResponse>(
    `/api/insights/monthly?${params.toString()}`,
    { method: "GET" },
  );
  return {
    ...response,
    recommendations: Array.isArray(response.recommendations)
      ? response.recommendations
      : [],
    metrics_snapshot: {
      ...response.metrics_snapshot,
      top_categories: Array.isArray(response.metrics_snapshot?.top_categories)
        ? response.metrics_snapshot.top_categories.map((cat) => ({
            ...cat,
            category: normalizeCategory(cat.category),
          }))
        : [],
      budget_alerts: Array.isArray(response.metrics_snapshot?.budget_alerts)
        ? response.metrics_snapshot.budget_alerts.map((alert) => ({
            ...alert,
            category: normalizeCategory(alert.category),
          }))
        : [],
    },
  };
}
