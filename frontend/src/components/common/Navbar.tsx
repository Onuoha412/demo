import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { roleHomePath } from "../../utils/roleRoutes";
import { PageContainer } from "./PageContainer";
import { logoutSession } from "../../services/auth";

export function Navbar() {
  const navigate = useNavigate();
  const { token, user, logout } = useAuthStore();
  const isCustomer = token && user?.role === "customer";
  const isStaff = token && user?.role === "staff";
  const isAdmin = token && user?.role === "admin";

  return (
    <header className="border-b border-ink/10 bg-cream">
      <PageContainer className="flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
        <Link to="/" className="text-xl font-black text-ink">
          Queue<span className="text-emerald-700">Less</span>
        </Link>
        <nav className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-sm">
          {!isStaff && !isAdmin && (
            <Link to="/services" className="text-ink/70 hover:text-ink">
              Services
            </Link>
          )}
          {isCustomer ? (
            <>
              <Link to="/history" className="text-ink/70 hover:text-ink">
                History
              </Link>
              <Link to="/notifications" className="text-ink/70 hover:text-ink">
                Notifications
              </Link>
              <Link to="/profile" className="text-ink/70 hover:text-ink">
                {user?.full_name ?? "Profile"}
              </Link>
              <button
                className="rounded-full bg-ink px-4 py-2 text-white"
                onClick={() => {
                  void logoutSession()
                    .catch((error: unknown) => console.error("Unable to revoke the server session.", error))
                    .finally(() => {
                      logout();
                      navigate("/");
                    });
                }}
              >
                Logout
              </button>
            </>
          ) : isStaff || isAdmin ? (
            <>
              <Link
                to={roleHomePath(user.role)}
                className="text-ink/70 hover:text-ink"
              >
                Dashboard
              </Link>
              {isAdmin && (
                <Link to="/admin/organizations" className="text-ink/70 hover:text-ink">
                  Manage
                </Link>
              )}
              <span className="text-ink/70">{user.full_name}</span>
              <button
                className="rounded-full bg-ink px-4 py-2 text-white"
                onClick={() => {
                  void logoutSession()
                    .catch((error: unknown) => console.error("Unable to revoke the server session.", error))
                    .finally(() => {
                      logout();
                      navigate("/");
                    });
                }}
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-ink/70 hover:text-ink">
                Customer login
              </Link>
              <Link to="/register" className="rounded-full bg-ink px-4 py-2 text-white">
                Register
              </Link>
              <Link to="/staff/login" className="text-ink/70 hover:text-ink">
                Staff
              </Link>
              <Link to="/admin/login" className="text-ink/70 hover:text-ink">
                Admin
              </Link>
            </>
          )}
        </nav>
      </PageContainer>
    </header>
  );
}
