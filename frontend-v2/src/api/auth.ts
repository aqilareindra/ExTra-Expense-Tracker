import type {
  AuthSuccessResponse,
  CurrentUserResponse,
  LoginRequest,
  LogoutResponse,
  RegisterRequest,
} from "../types/api";
import { requestJson } from "./client";

export async function getCurrentUser(): Promise<CurrentUserResponse> {
  return requestJson<CurrentUserResponse>("/api/auth/me", {
    method: "GET",
  });
}

export async function loginUser(
  payload: LoginRequest,
): Promise<AuthSuccessResponse> {
  return requestJson<AuthSuccessResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function registerUser(
  payload: RegisterRequest,
): Promise<AuthSuccessResponse> {
  return requestJson<AuthSuccessResponse>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function logoutUser(): Promise<LogoutResponse> {
  return requestJson<LogoutResponse>("/api/auth/logout", {
    method: "POST",
  });
}
