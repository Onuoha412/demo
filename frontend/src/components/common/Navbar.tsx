import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { roleHomePath } from "../../utils/roleRoutes";
import { PageContainer } from "./PageContainer";
import { logoutSession } from "../../services/auth";
import { useServerClock } from "../../hooks/useServerClock";

export function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuPath, setMobileMenuPath] = useState<string | null>(null);
  const mobileMenuOpen = mobileMenuPath === location.pathname;
  const { token, user, logout } = useAuthStore();
  const serverNow = useServerClock();
  const isCustomer = token && user?.role === "customer";
  const isStaff = token && user?.role === "staff";
  const isAdmin = token && user?.role === "admin";
  const isSuperAdmin = token && user?.role === "super_admin";

  const handleLogout = () => {
    void logoutSession()
      .catch((error: unknown) => console.error("Unable to revoke the server session.", error))
      .finally(() => {
        logout();
        navigate("/");
      });
  };

  const mobileLinkClass =
    "rounded-xl px-4 py-3 text-sm font-semibold text-ink/75 transition hover:bg-emerald-50 hover:text-ink";

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenuPath(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileMenuOpen]);

  return (
    <header className="sticky top-0 z-40 border-b border-ink/10 bg-cream/95 backdrop-blur">
      <PageContainer className="relative flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
        <Link to="/" className="text-xl font-black text-ink" aria-label="QueueLess home">
          Queue<span className="text-emerald-700">Less</span>
        </Link>
        <time
          className="hidden text-xs font-medium text-ink/60 lg:block"
          dateTime={serverNow.toISOString()}
          title="Synchronized with QueueLess server time"
        >
          Server time {serverNow.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </time>
        <nav
          aria-label="Main navigation"
          className="hidden flex-wrap items-center justify-end gap-x-3 gap-y-1 text-sm md:flex"
        >
          {!isStaff && !isAdmin && !isSuperAdmin && (
            <>
              <Link to="/services" className="text-ink/70 hover:text-ink">
                Services
              </Link>
              <Link to="/scan" className="text-ink/70 hover:text-ink">
                Scan QR
              </Link>
            </>
          )}
          {isCustomer ? (
            <>
              <Link to="/history" className="text-ink/70 hover:text-ink">
                History
              </Link>
              <Link to="/appointments" className="text-ink/70 hover:text-ink">
                Appointments
              </Link>
              <Link to="/notifications" className="text-ink/70 hover:text-ink">
                Notifications
              </Link>
              <Link to="/feedback/history" className="text-ink/70 hover:text-ink">
                Feedback history
              </Link>
              <Link to="/profile" className="text-ink/70 hover:text-ink">
                {user?.full_name ?? "Profile"}
              </Link>
              <button
                className="rounded-full bg-ink px-4 py-2 text-white"
                onClick={handleLogout}
              >
                Logout
              </button>
            </>
          ) : isStaff || isAdmin || isSuperAdmin ? (
            <>
              <NavLink
                to={roleHomePath(user.role)}
                className={({ isActive }) =>
                  isActive
                    ? "font-bold text-emerald-800"
                    : "text-ink/70 hover:text-ink"
                }
              >
                Dashboard
              </NavLink>
              {isStaff && (
                <>
                  <Link to="/feedback/history" className="text-ink/70 hover:text-ink">
                    My feedback
                  </Link>
                  <NavLink
                    to="/staff/queue"
                    className={({ isActive }) =>
                      isActive
                        ? "font-bold text-emerald-800"
                        : "text-ink/70 hover:text-ink"
                    }
                  >
                    Queue
                  </NavLink>
                  <NavLink
                    to="/staff/customers"
                    className={({ isActive }) =>
                      isActive
                        ? "font-bold text-emerald-800"
                        : "text-ink/70 hover:text-ink"
                    }
                  >
                    Customers
                  </NavLink>
                  <NavLink
                    to="/staff/history"
                    className={({ isActive }) =>
                      isActive
                        ? "font-bold text-emerald-800"
                        : "text-ink/70 hover:text-ink"
                    }
                  >
                    History
                  </NavLink>
                </>
              )}
              {(isAdmin || isSuperAdmin) && (
                <>
                  <NavLink
                    to={isSuperAdmin ? "/super-admin/feedback" : "/admin/feedback"}
                    className={({ isActive }) =>
                      isActive
                        ? "font-bold text-emerald-800"
                        : "text-ink/70 hover:text-ink"
                    }
                  >
                    Feedback center
                  </NavLink>
                  <Link to="/feedback/history" className="text-ink/70 hover:text-ink">
                    My feedback
                  </Link>
                  <Link
                    to={isSuperAdmin ? "/super-admin/organizations" : "/admin/organizations"}
                    className="text-ink/70 hover:text-ink"
                  >
                    Manage
                  </Link>
                  {isAdmin && (
                    <Link to="/admin/announcements" className="text-ink/70 hover:text-ink">
                      Announcements
                    </Link>
                  )}
                  {isSuperAdmin && (
                    <Link to="/super-admin/operations" className="text-ink/70 hover:text-ink">
                      Operations
                    </Link>
                  )}
                  <Link
                    to="/admin/migrations"
                    className="text-ink/70 hover:text-ink"
                  >
                    Migration Center
                  </Link>
                </>
              )}
              <Link to="/profile" className="text-ink/70 hover:text-ink">
                Profile
              </Link>
              <span className="text-ink/70">{user.full_name}</span>
              <button
                className="rounded-full bg-ink px-4 py-2 text-white"
                onClick={handleLogout}
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
              <Link to="/super-admin/login" className="text-ink/70 hover:text-ink">
                Super Admin
              </Link>
            </>
          )}
        </nav>
        <button
          aria-controls="mobile-navigation"
          aria-expanded={mobileMenuOpen}
          aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
          className="grid h-10 w-10 place-items-center rounded-full border border-ink/10 text-ink transition hover:bg-ink/5 focus-visible:outline-emerald-700 md:hidden"
          onClick={() => setMobileMenuPath(mobileMenuOpen ? null : location.pathname)}
          type="button"
        >
          {mobileMenuOpen ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}
        </button>
        <nav
          aria-label="Mobile navigation"
          className="absolute inset-x-0 top-full z-50 border-b border-ink/10 bg-cream px-6 pb-4 pt-2 shadow-xl md:hidden"
          hidden={!mobileMenuOpen}
          id="mobile-navigation"
        >
            <div className="grid grid-cols-2 gap-1">
              {!isStaff && !isAdmin && !isSuperAdmin && (
                <>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/services">
                    Services
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/scan">
                    Scan QR
                  </Link>
                </>
              )}
              {isCustomer ? (
                <>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/history">
                    History
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/appointments">
                    Appointments
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/notifications">
                    Notifications
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/feedback/history">
                    Feedback history
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/profile">
                    {user?.full_name ?? "Profile"}
                  </Link>
                </>
              ) : isStaff || isAdmin || isSuperAdmin ? (
                <>
                  <Link
                    className={mobileLinkClass}
                    onClick={() => setMobileMenuPath(null)}
                    to={roleHomePath(user.role)}
                  >
                    Dashboard
                  </Link>
                  {isStaff && (
                    <>
                      <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/staff/queue">
                        Queue
                      </Link>
                      <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/staff/customers">
                        Customers
                      </Link>
                      <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/staff/history">
                        History
                      </Link>
                    </>
                  )}
                  {(isAdmin || isSuperAdmin) && (
                    <>
                      <Link
                        className={mobileLinkClass}
                        onClick={() => setMobileMenuPath(null)}
                        to={isSuperAdmin ? "/super-admin/feedback" : "/admin/feedback"}
                      >
                        Feedback center
                      </Link>
                      <Link
                        className={mobileLinkClass}
                        onClick={() => setMobileMenuPath(null)}
                        to={isSuperAdmin ? "/super-admin/organizations" : "/admin/organizations"}
                      >
                        Manage
                      </Link>
                      <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/admin/migrations">
                        Migration Center
                      </Link>
                    </>
                  )}
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/feedback/history">
                    My feedback
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/profile">
                    Profile
                  </Link>
                </>
              ) : (
                <>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/login">
                    Customer login
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/register">
                    Create account
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/staff/login">
                    Staff sign in
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/admin/login">
                    Admin sign in
                  </Link>
                  <Link className={mobileLinkClass} onClick={() => setMobileMenuPath(null)} to="/super-admin/login">
                    Super admin
                  </Link>
                </>
              )}
              {(isCustomer || isStaff || isAdmin || isSuperAdmin) && (
                <button
                  className="col-span-2 mt-1 rounded-xl bg-ink px-4 py-3 text-left text-sm font-bold text-white"
                  onClick={handleLogout}
                  type="button"
                >
                  Log out
                </button>
              )}
            </div>
        </nav>
      </PageContainer>
    </header>
  );
}
