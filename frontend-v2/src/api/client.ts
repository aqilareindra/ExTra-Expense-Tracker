import type { ApiErrorResponse, ValidationErrorDetail } from "../types/api";

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly errorCode: string;
  public readonly details: ValidationErrorDetail[];

  constructor(
    message: string,
    status = 0,
    errorCode = "UNKNOWN_ERROR",
    details: ValidationErrorDetail[] = [],
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

const FALLBACK_STATUS_MESSAGES: Record<number, string> = {
  400: "Permintaan tidak valid. Periksa kembali file atau data yang dikirim.",
  413: "Ukuran file melebihi batas maksimal 5 MB.",
  422: "Data belum lolos validasi. Periksa kembali input yang ditandai.",
  429: "Batas permintaan layanan AI tercapai sementara. Silakan coba lagi sebentar.",
  500: "Terjadi kesalahan internal pada server ExTra.",
  502: "Format respons layanan AI tidak dapat diproses. Silakan unggah ulang.",
  503: "Layanan AI sedang sibuk atau tidak dapat dijangkau sementara. Silakan coba lagi.",
};

function isApiErrorPayload(value: unknown): value is ApiErrorResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    (value as { status: unknown }).status === "error"
  );
}

export async function requestJson<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new ApiClientError(
      "Tidak dapat terhubung ke server ExTra. Pastikan backend FastAPI sedang berjalan.",
      0,
      "NETWORK_ERROR",
      [],
    );
  }

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }

  if (!response.ok || isApiErrorPayload(payload)) {
    const errorPayload = isApiErrorPayload(payload) ? payload : null;
    const rawMsg = errorPayload?.message?.trim();
    const fallbackMsg =
      FALLBACK_STATUS_MESSAGES[response.status] ??
      `Permintaan gagal diproses (HTTP ${response.status}).`;

    throw new ApiClientError(
      rawMsg && rawMsg.length > 0 ? rawMsg : fallbackMsg,
      response.status,
      errorPayload?.error_code ?? `HTTP_${response.status}`,
      Array.isArray(errorPayload?.details) ? errorPayload.details : [],
    );
  }

  if (payload === null) {
    throw new ApiClientError(
      "Respons server tidak berformat JSON yang valid.",
      response.status,
      "INVALID_SERVER_RESPONSE",
      [],
    );
  }

  return payload as T;
}
