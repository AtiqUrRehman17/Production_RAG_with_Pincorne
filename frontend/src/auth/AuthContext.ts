import { createContext } from "react";

import type { LoginRequest, RegisterRequest, TokenResponse, User } from "../api/types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthState {
  status: AuthStatus; // "loading" while a page reload restores the session from the cookie
  user: User | null;
  restored: boolean; // signed in from the refresh cookie when the page loaded (not by the login form)
  login: (body: LoginRequest) => Promise<TokenResponse>;
  register: (body: RegisterRequest) => Promise<TokenResponse>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  deleteAccount: (password: string) => Promise<void>;
  setUser: (user: User) => void; // after the name was changed
}

export const AuthContext = createContext<AuthState | null>(null);
