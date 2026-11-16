import { createBrowserRouter, Navigate } from "react-router";

import { GuestOnly, RequireAdmin, RequireAuth } from "./auth/guards";
import { AppLayout } from "./components/AppLayout";
import { AccountPage } from "./pages/AccountPage";
import { AdminPage } from "./pages/admin/AdminPage";
import { LoginPage } from "./pages/auth/LoginPage";
import { RegisterPage } from "./pages/auth/RegisterPage";
import { ChatPage } from "./pages/chat/ChatPage";
import { DocumentsPage } from "./pages/documents/DocumentsPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    element: <GuestOnly />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [{
      element: <AppLayout />,
      children: [
        { index: true, element: <Navigate to="/chat" replace /> },
        // One route for a new chat and an existing one, so the page (and a streaming answer) stays mounted
        { path: "/chat/:conversationId?", element: <ChatPage /> },
        { path: "/documents", element: <DocumentsPage /> },
        { path: "/account", element: <AccountPage /> },
        { element: <RequireAdmin />, children: [{ path: "/admin", element: <AdminPage /> }] },
      ],
    }],
  },
  { path: "*", element: <NotFoundPage /> },
]);
