import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import * as authApi from "../api/auth";
import { onSessionEnded, refreshSession } from "../api/client";
import type { LoginRequest, RegisterRequest, User } from "../api/types";
import { AuthContext, type AuthState, type AuthStatus } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUserState] = useState<User | null>(null);
  const [restored, setRestored] = useState(false);

  const signIn = useCallback((next: User) => {
    setUserState(next);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(() => {
    setUserState(null);
    setStatus("anonymous");
    setRestored(false);
    queryClient.clear(); // nothing of this user stays cached for the next one
  }, [queryClient]);

  useEffect(() => {
    onSessionEnded(signOut);
    // After a page reload the access token is gone; the refresh cookie brings the session back
    refreshSession().then((tokens) => {
      setRestored(true);
      signIn(tokens.user);
    }, () => signOut());
  }, [signIn, signOut]);

  const login = useCallback(async (body: LoginRequest) => {
    const tokens = await authApi.login(body);
    queryClient.clear();
    signIn(tokens.user);
    return tokens;
  }, [queryClient, signIn]);

  const register = useCallback(async (body: RegisterRequest) => {
    const tokens = await authApi.register(body);
    queryClient.clear();
    signIn(tokens.user);
    return tokens;
  }, [queryClient, signIn]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      signOut();
    }
  }, [signOut]);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const tokens = await authApi.changePassword(currentPassword, newPassword);
    signIn(tokens.user);
  }, [signIn]);

  const deleteAccount = useCallback(async (password: string) => {
    await authApi.deleteAccount(password);
    signOut();
  }, [signOut]);

  const value = useMemo<AuthState>(() => ({
    status, user, restored, login, register, logout, changePassword, deleteAccount, setUser: signIn,
  }), [status, user, restored, login, register, logout, changePassword, deleteAccount, signIn]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
