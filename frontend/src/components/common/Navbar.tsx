import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { PageContainer } from "./PageContainer";

export function Navbar() {
  const navigate = useNavigate();
  const { token, user, logout } = useAuthStore();

  return (
    <header className="border-b border-ink/10 bg-cream">
      <PageContainer className="flex h-16 items-center justify-between">
        <Link to="/" className="text-xl font-black text-ink">
          Queue<span className="text-emerald-700">Less</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/services" className="text-ink/70 hover:text-ink">
            Services
          </Link>
          {token ? (
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
                  logout();
                  navigate("/login");
                }}
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-ink/70 hover:text-ink">
                Login
              </Link>
              <Link to="/register" className="rounded-full bg-ink px-4 py-2 text-white">
                Register
              </Link>
            </>
          )}
        </nav>
      </PageContainer>
    </header>
  );
}
