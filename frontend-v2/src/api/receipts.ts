import { normalizeCategory } from "../constants/categories";
import type { ReceiptExtractResponse } from "../types/api";
import { requestJson } from "./client";

export async function extractReceiptImage(
  file: File,
): Promise<ReceiptExtractResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await requestJson<ReceiptExtractResponse>(
    "/api/receipts/extract",
    {
      method: "POST",
      body: formData,
    },
  );

  return {
    ...response,
    warnings: Array.isArray(response.warnings) ? response.warnings : [],
    temp_image_token: response.temp_image_token ?? null,
    data: {
      date: response.data?.date ?? null,
      items: Array.isArray(response.data?.items)
        ? response.data.items.map((item) => ({
            name: item.name,
            price: item.price,
            category: normalizeCategory(item.category),
          }))
        : [],
    },
  };
}
