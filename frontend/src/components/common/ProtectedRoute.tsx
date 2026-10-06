import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";

export function ProtectedRoute({ children, allowedRoles }: { children: ReactNode; allowedRoles?: Array<"customer" | "staff" | "admin"> }) {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  if (!token || (allowedRoles && (!user || !allowedRoles.includes(user.role)))) {
    return <Navigate to={allowedRoles?.includes("admin") ? "/admin/login" : allowedRoles ? "/staff/login" : "/login"} replace state={{ from: `${location.pathname}${location.search}${location.hash}` }} />;
  }
  return <>{children}</>;
}
