import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import type { User } from "../../types/api";
import { roleHomePath, roleLoginPath } from "../../utils/roleRoutes";

export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: ReactNode;
  allowedRoles?: User["role"][];
}) {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const ready = useAuthStore((state) => state.ready);
  const location = useLocation();
  if (!ready) return <p className="p-8 text-center">Restoring your secure session...</p>;
  if (!token || !user) {
    const loginPath = allowedRoles?.length === 1 ? roleLoginPath(allowedRoles[0]) : "/login";
    return (
      <Navigate
        to={loginPath}
        replace
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
      />
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={roleHomePath(user.role)} replace />;
  }

  return <>{children}</>;
}
