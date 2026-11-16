import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { AuthProvider } from "./auth/AuthProvider";
import { Toaster } from "./components/Toaster";
import "./index.css";
import { queryClient } from "./lib/queryClient";
import "./lib/theme";
import { router } from "./router";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
