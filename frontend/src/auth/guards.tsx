import { Navigate, Outlet, useLocation } from "react-router";

import { FullPageSpinner } from "../components/FullPageSpinner";
import { useAuth } from "./useAuth";

/** Logged-in users only; others go to /login and come back afterwards. */
export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullPageSpinner />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

/** Admins only (the backend checks too; this just hides the pages). */
export function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}

/** Login and register: someone already logged in when the page loaded goes straight to the app.
 *  After the form logs someone in, the page itself navigates (e.g. a new account to /documents). */
export function GuestOnly() {
  const { status, restored } = useAuth();
  if (status === "loading") return <FullPageSpinner />;
  if (status === "authenticated" && restored) return <Navigate to="/" replace />;
  return <Outlet />;
}
