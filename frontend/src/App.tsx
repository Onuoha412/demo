import { lazy, Suspense, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Navbar } from "./components/common/Navbar";
import { FeedbackEntryPoint } from "./components/common/FeedbackEntryPoint";
import { LoadingState } from "./components/common/LoadingState";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { HomePage } from "./pages/customer/HomePage";
import { useAuthStore } from "./store/authStore";
import { roleHomePath } from "./utils/roleRoutes";
import { me } from "./services/auth";
import { ApiError } from "./services/api";
import { useAppRealtime } from "./hooks/useAppRealtime";

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
const ScanQRCodePage = lazy(() =>
  import("./pages/customer/ScanQRCodePage").then((module) => ({
    default: module.ScanQRCodePage,
  })),
);
const AppointmentsPage = lazy(() =>
  import("./pages/customer/AppointmentsPage").then((module) => ({
    default: module.AppointmentsPage,
  })),
);
const AppointmentSlotsPage = lazy(() =>
  import("./pages/admin/AppointmentSlotsPage").then((module) => ({
    default: module.AppointmentSlotsPage,
  })),
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
const SuperAdminLoginPage = lazy(() =>
  import("./pages/admin/SuperAdminLoginPage").then((module) => ({
    default: module.SuperAdminLoginPage,
  })),
);
const SuperAdminDashboardPage = lazy(() =>
  import("./pages/admin/SuperAdminDashboardPage").then((module) => ({
    default: module.SuperAdminDashboardPage,
  })),
);
const SuperAdminAuditPage = lazy(() =>
  import("./pages/admin/SuperAdminAuditPage").then((module) => ({
    default: module.SuperAdminAuditPage,
  })),
);
const SuperAdminOperationsPage = lazy(() =>
  import("./pages/admin/SuperAdminOperationsPage").then((module) => ({
    default: module.SuperAdminOperationsPage,
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
const OrganizationAnnouncementsPage = lazy(() =>
  import("./pages/admin/OrganizationAnnouncementsPage").then((module) => ({
    default: module.OrganizationAnnouncementsPage,
  })),
);
const MigrationCenterPage = lazy(() =>
  import("./pages/admin/MigrationCenterPage").then((module) => ({
    default: module.MigrationCenterPage,
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
const FeedbackCenterPage = lazy(() =>
  import("./pages/FeedbackCenterPage").then((module) => ({
    default: module.FeedbackCenterPage,
  })),
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
    let retryTimer: number | undefined;
    let retryCount = 0;
    const restore = async () => {
      try {
        const user = await me(token);
        const remembered =
          typeof localStorage !== "undefined" &&
          localStorage.getItem("queueless.remembered") === token;
        if (active) setAuth(user, token, remembered);
      } catch (error: unknown) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) {
          logout();
          return;
        }
        console.error("Unable to restore the QueueLess session; retrying.", error);
        retryTimer = window.setTimeout(
          () => void restore(),
          Math.min(30_000, 1_000 * 2 ** retryCount++),
        );
      }
    };
    const retryWhenOnline = () => {
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      void restore();
    };
    window.addEventListener("online", retryWhenOnline);
    void restore();
    return () => {
      active = false;
      window.removeEventListener("online", retryWhenOnline);
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
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

function AppRealtimeConnection() {
  const token = useAuthStore((state) => state.token);
  useAppRealtime(token);
  return null;
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <AuthSessionBootstrap />
      <SessionDataIsolation />
      <AppRealtimeConnection />
      <div className="min-h-screen bg-cream text-ink">
        <Navbar />
        <FeedbackEntryPoint />
        <Suspense fallback={<LoadingState label="Loading page..." />}>
          <Routes>
            <Route path="/" element={<RoleHomeRoute />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/scan" element={<ScanQRCodePage />} />
            <Route path="/services/:serviceId" element={<ServiceDetailPage />} />
            <Route
              path="/services/:serviceId/appointments"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <AppointmentsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/appointments"
              element={
                <ProtectedRoute allowedRoles={["customer"]}>
                  <AppointmentsPage />
                </ProtectedRoute>
              }
            />
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
                <ProtectedRoute allowedRoles={["customer", "staff", "admin", "super_admin"]}>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route path="/notifications" element={<ProtectedRoute allowedRoles={["customer"]}><NotificationsPage /></ProtectedRoute>} />
            <Route
              path="/feedback/history"
              element={
                <ProtectedRoute allowedRoles={["customer", "staff", "admin", "super_admin"]}>
                  <FeedbackCenterPage />
                </ProtectedRoute>
              }
            />
            <Route path="/staff/login" element={<StaffLoginPage />} />
            <Route path="/staff/forgot-password" element={<ForgotPasswordPage loginPath="/staff/login" />} />
            <Route path="/staff/dashboard" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/queue" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/customers" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/staff/history" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
            <Route path="/admin/login" element={<AdminLoginPage />} />
            <Route path="/admin/forgot-password" element={<ForgotPasswordPage loginPath="/admin/login" />} />
            <Route path="/admin/dashboard" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
            <Route path="/admin/announcements" element={<ProtectedRoute allowedRoles={["admin"]}><OrganizationAnnouncementsPage /></ProtectedRoute>} />
            <Route path="/admin/migrations" element={<ProtectedRoute allowedRoles={["admin", "super_admin"]}><MigrationCenterPage /></ProtectedRoute>} />
            <Route path="/admin/queues/:queueId/entries" element={<ProtectedRoute allowedRoles={["admin"]}><AdminQueuePage /></ProtectedRoute>} />
            <Route path="/admin/:resource" element={<ProtectedRoute allowedRoles={["admin"]}><AdminResourcePage /></ProtectedRoute>} />
            <Route
              path="/admin/services/:serviceId/appointments"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <AppointmentSlotsPage />
                </ProtectedRoute>
              }
            />
            <Route path="/admin/analytics" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
            <Route path="/admin/feedback" element={<ProtectedRoute allowedRoles={["admin"]}><FeedbackCenterPage /></ProtectedRoute>} />
            <Route path="/super-admin/login" element={<SuperAdminLoginPage />} />
            <Route path="/super-admin/forgot-password" element={<ForgotPasswordPage loginPath="/super-admin/login" />} />
            <Route path="/super-admin/dashboard" element={<ProtectedRoute allowedRoles={["super_admin"]}><SuperAdminDashboardPage /></ProtectedRoute>} />
            <Route path="/super-admin/audit-logs" element={<ProtectedRoute allowedRoles={["super_admin"]}><SuperAdminAuditPage /></ProtectedRoute>} />
            <Route path="/super-admin/operations" element={<ProtectedRoute allowedRoles={["super_admin"]}><SuperAdminOperationsPage /></ProtectedRoute>} />
            <Route path="/super-admin/feedback" element={<ProtectedRoute allowedRoles={["super_admin"]}><FeedbackCenterPage /></ProtectedRoute>} />
            <Route path="/super-admin/queues/:queueId/entries" element={<ProtectedRoute allowedRoles={["super_admin"]}><AdminQueuePage /></ProtectedRoute>} />
            <Route path="/super-admin/:resource" element={<ProtectedRoute allowedRoles={["super_admin"]}><AdminResourcePage /></ProtectedRoute>} />
            <Route
              path="/super-admin/services/:serviceId/appointments"
              element={
                <ProtectedRoute allowedRoles={["super_admin"]}>
                  <AppointmentSlotsPage />
                </ProtectedRoute>
              }
            />
            <Route path="/display/:queueId" element={<DisplayPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
    </BrowserRouter>
  );
}
