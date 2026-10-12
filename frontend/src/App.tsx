import { lazy, Suspense, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Navbar } from "./components/common/Navbar";
import { LoadingState } from "./components/common/LoadingState";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { HomePage } from "./pages/customer/HomePage";
import { useAuthStore } from "./store/authStore";
import { roleHomePath } from "./utils/roleRoutes";
import { me } from "./services/auth";
import { ApiError } from "./services/api";

const LoginPage = lazy(() =>
  import("./pages/customer/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const RegisterPage = lazy(() =>
  import("./pages/customer/RegisterPage").then((module) => ({ default: module.RegisterPage })),
);
const ForgotPasswordPage = lazy(() =>
  import("./pages/auth/ForgotPasswordPage").then((module) => ({
    default: module.ForgotPasswordPage,
  })),
);
const ResetPasswordPage = lazy(() =>
  import("./pages/auth/ResetPasswordPage").then((module) => ({
    default: module.ResetPasswordPage,
  })),
);
const ServicesPage = lazy(() =>
  import("./pages/customer/ServicesPage").then((module) => ({ default: module.ServicesPage })),
);
const ServiceDetailPage = lazy(() =>
  import("./pages/customer/ServiceDetailPage").then((module) => ({
    default: module.ServiceDetailPage,
  })),
);
const JoinQueuePage = lazy(() =>
  import("./pages/customer/JoinQueuePage").then((module) => ({
    default: module.JoinQueuePage,
  })),
);
const QueuePage = lazy(() =>
  import("./pages/customer/QueuePage").then((module) => ({ default: module.QueuePage })),
);
const HistoryPage = lazy(() =>
  import("./pages/customer/HistoryPage").then((module) => ({ default: module.HistoryPage })),
);
const ProfilePage = lazy(() =>
  import("./pages/customer/ProfilePage").then((module) => ({ default: module.ProfilePage })),
);
const NotificationsPage = lazy(() =>
  import("./pages/customer/NotificationsPage").then((module) => ({
    default: module.NotificationsPage,
  })),
);
const StaffDashboardPage = lazy(() =>
  import("./pages/staff/StaffDashboardPage").then((module) => ({
    default: module.StaffDashboardPage,
  })),
);
const StaffLoginPage = lazy(() =>
  import("./pages/staff/StaffLoginPage").then((module) => ({
    default: module.StaffLoginPage,
  })),
);
const AdminLoginPage = lazy(() =>
  import("./pages/admin/AdminLoginPage").then((module) => ({
    default: module.AdminLoginPage,
  })),
);
const AdminResourcePage = lazy(() =>
  import("./pages/admin/AdminResourcePage").then((module) => ({
    default: module.AdminResourcePage,
  })),
);
const AdminDashboardPage = lazy(() =>
  import("./pages/admin/AdminDashboardPage").then((module) => ({
    default: module.AdminDashboardPage,
  })),
);
const AdminQueuePage = lazy(() =>
  import("./pages/admin/AdminQueuePage").then((module) => ({
    default: module.AdminQueuePage,
  })),
);
const DisplayPage = lazy(() =>
  import("./pages/display/DisplayPage").then((module) => ({ default: module.DisplayPage })),
);

function RoleHomeRoute() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const ready = useAuthStore((state) => state.ready);

  if (!ready) return <HomePage />;
  if (!token || !user || user.role === "customer") return <HomePage />;
  return <Navigate to={roleHomePath(user.role)} replace />;
}

function AuthSessionBootstrap() {
  const token = useAuthStore((state) => state.token);
  const setAuth = useAuthStore((state) => state.setAuth);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    if (useAuthStore.getState().ready) return;
    if (!token) {
      useAuthStore.getState().setReady();
      return;
    }
    let active = true;
    void me(token)
      .then((user) => {
        if (active) setAuth(user, token);
      })
      .catch((error: unknown) => {
        if (!active) return;
        logout();
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.error("Unable to restore the QueueLess session.", error);
        }
      });
    return () => {
      active = false;
    };
  }, [logout, setAuth, token]);

  return null;
}

function SessionDataIsolation() {
  const queryClient = useQueryClient();
  const userId = useAuthStore((state) => state.user?.id);
  const previousUserId = useRef(userId);

  useEffect(() => {
    if (previousUserId.current !== userId) queryClient.clear();
    previousUserId.current = userId;
  }, [queryClient, userId]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <AuthSessionBootstrap />
      <SessionDataIsolation />
      <div className="min-h-screen bg-cream text-ink">
        <Navbar />
        <Suspense fallback={<LoadingState label="Loading page..." />}>
          <Routes>
            <Route path="/" element={<RoleHomeRoute />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/services/:serviceId" element={<ServiceDetailPage />} />
            <Route
              path="/join/:serviceId"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <JoinQueuePage />
                </ProtectedRoute>
              }
            />
            <Route path="/join/:branchId/:serviceId" element={<ProtectedRoute allowedRoles={["customer"]}><JoinQueuePage /></ProtectedRoute>} />
            <Route
              path="/queue/:entryId"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <QueuePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <HistoryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route path="/notifications" element={<ProtectedRoute allowedRoles={["customer"]}><NotificationsPage /></ProtectedRoute>} />
            <Route path="/staff/login" element={<StaffLoginPage />} />
            <Route path="/staff/dashboard" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/queue" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/customers" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/history" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/admin/login" element={<AdminLoginPage />} />
            <Route path="/admin/dashboard" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
            <Route path="/admin/queues/:queueId/entries" element={<ProtectedRoute allowedRoles={["admin"]}><AdminQueuePage /></ProtectedRoute>} />
            <Route path="/admin/:resource" element={<ProtectedRoute allowedRoles={["admin"]}><AdminResourcePage /></ProtectedRoute>} />
            <Route path="/admin/analytics" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
            <Route path="/display/:queueId" element={<DisplayPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
    </BrowserRouter>
  );
}
