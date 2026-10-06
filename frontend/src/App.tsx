import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Navbar } from "./components/common/Navbar";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { HomePage } from "./pages/customer/HomePage";
import { HistoryPage } from "./pages/customer/HistoryPage";
import { JoinQueuePage } from "./pages/customer/JoinQueuePage";
import { LoginPage } from "./pages/customer/LoginPage";
import { ProfilePage } from "./pages/customer/ProfilePage";
import { QueuePage } from "./pages/customer/QueuePage";
import { RegisterPage } from "./pages/customer/RegisterPage";
import { ServiceDetailPage } from "./pages/customer/ServiceDetailPage";
import { ServicesPage } from "./pages/customer/ServicesPage";
import { StaffDashboardPage } from "./pages/staff/StaffDashboardPage";
import { StaffLoginPage } from "./pages/staff/StaffLoginPage";
import { AdminLoginPage } from "./pages/admin/AdminLoginPage";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { AdminResourcePage } from "./pages/admin/AdminResourcePage";
import { DisplayPage } from "./pages/display/DisplayPage";
import { NotificationsPage } from "./pages/customer/NotificationsPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-cream text-ink">
        <Navbar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/services" element={<ServicesPage />} />
          <Route path="/services/:serviceId" element={<ServiceDetailPage />} />
          <Route
            path="/join/:serviceId"
            element={
              <ProtectedRoute>
                <JoinQueuePage />
              </ProtectedRoute>
            }
          />
          <Route path="/join/:branchId/:serviceId" element={<ProtectedRoute><JoinQueuePage /></ProtectedRoute>} />
          <Route
            path="/queue/:entryId"
            element={
              <ProtectedRoute>
                <QueuePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="/staff/login" element={<StaffLoginPage />} />
          <Route path="/staff/dashboard" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
          <Route path="/staff/queue" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
          <Route path="/staff/customers" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
          <Route path="/staff/history" element={<ProtectedRoute allowedRoles={["staff"]}><StaffDashboardPage /></ProtectedRoute>} />
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/admin/dashboard" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
          {["organizations", "branches", "services", "counters", "queues", "users"].map((resource) => <Route key={resource} path={`/admin/${resource}`} element={<ProtectedRoute allowedRoles={["admin"]}><AdminResourcePage /></ProtectedRoute>} />)}
          <Route path="/admin/analytics" element={<ProtectedRoute allowedRoles={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
          <Route path="/display/:queueId" element={<DisplayPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
