// =============================================================================
// PH Agent Hub — Router
// =============================================================================
// React Router createBrowserRouter; routes: /login, /chat, /chat/:sessionId,
// /admin/*, all protected via RouteGuard.
// =============================================================================

import { createBrowserRouter } from "react-router-dom";
import { RouteGuard } from "../shared/components/RouteGuard";
import LoginPage from "../features/auth/LoginPage";
import ChatPage from "../features/chat/routes/ChatPage";
import AdminApp from "../features/admin/routes/AdminApp";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <RouteGuard />,
    children: [
      {
        path: "/chat",
        element: <ChatPage />,
      },
      {
        path: "/chat/:sessionId",
        element: <ChatPage />,
      },
    ],
  },
  {
    element: <RouteGuard adminOnly />,
    children: [
      {
        path: "/admin/*",
        element: <AdminApp />,
      },
    ],
  },
  {
    path: "*",
    element: <LoginPage />,
  },
]);

export default router;
