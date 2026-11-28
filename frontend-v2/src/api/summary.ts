import { normalizeCategory } from "../constants/categories";
import type { MonthlySummaryResponse } from "../types/api";
import { requestJson } from "./client";

export async function getMonthlySummary(
  month: number,
  year: number,
): Promise<MonthlySummaryResponse> {
  const params = new URLSearchParams({
    month: String(month),
    year: String(year),
  });
  const response = await requestJson<MonthlySummaryResponse>(
    `/api/summary/monthly?${params.toString()}`,
    {
      method: "GET",
    },
  );
  return {
    ...response,
    total_income: Number(response.total_income ?? 0),
    net_balance: Number(response.net_balance ?? 0),
    daily_breakdown: Array.isArray(response.daily_breakdown)
      ? response.daily_breakdown
      : [],
    category_breakdown: Array.isArray(response.category_breakdown)
      ? response.category_breakdown.map((entry) => ({
          ...entry,
          category: normalizeCategory(entry.category),
        }))
      : [],
  };
}
