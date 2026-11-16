import { request, setAccessToken } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse, User } from "./types";

async function keepToken(tokens: Promise<TokenResponse>): Promise<TokenResponse> {
  const result = await tokens;
  setAccessToken(result.access_token);
  return result;
}

export function register(body: RegisterRequest): Promise<TokenResponse> {
  return keepToken(request("/auth/register", { body, auth: false }));
}

export function login(body: LoginRequest): Promise<TokenResponse> {
  return keepToken(request("/auth/login", { body, auth: false }));
}

export async function logout(): Promise<void> {
  try {
    await request("/auth/logout", { method: "POST", auth: false });
  } finally {
    setAccessToken(null);
  }
}

export function getMe(): Promise<User> {
  return request("/auth/me");
}

export function updateMe(name: string): Promise<User> {
  return request("/auth/me", { method: "PATCH", body: { name } });
}

/** Logs out your other devices; this one gets new tokens. */
export function changePassword(currentPassword: string, newPassword: string): Promise<TokenResponse> {
  return keepToken(request("/auth/change-password", {
    body: { current_password: currentPassword, new_password: newPassword },
  }));
}

/** Deletes the account with all its documents and chats. */
export async function deleteAccount(password: string): Promise<void> {
  await request("/auth/me", { method: "DELETE", body: { password } });
  setAccessToken(null);
}
