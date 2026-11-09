import { apiRequest } from "./api";

export type AppointmentSlot = {
  id: string;
  service_id: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  booked_count: number;
  is_open: boolean;
};

export type Appointment = {
  id: string;
  slot_id: string;
  service_id: string;
  service_name: string;
  starts_at: string;
  ends_at: string;
  status: "booked" | "checked_in" | "cancelled" | "completed" | "no_show";
  checked_in_at: string | null;
  created_at: string;
};

export function listAvailableAppointmentSlots(serviceId: string, token: string) {
  const query = new URLSearchParams({ service_id: serviceId });
  return apiRequest<AppointmentSlot[]>(
    `/api/v1/customers/appointment-slots?${query}`,
    {},
    token,
  );
}

export function listCustomerAppointments(token: string) {
  return apiRequest<Appointment[]>("/api/v1/customers/appointments", {}, token);
}

export function bookAppointment(slotId: string, token: string) {
  return apiRequest<Appointment>(
    "/api/v1/customers/appointments",
    { method: "POST", body: JSON.stringify({ slot_id: slotId }) },
    token,
  );
}

export function cancelAppointment(appointmentId: string, token: string) {
  return apiRequest<Appointment>(
    `/api/v1/customers/appointments/${encodeURIComponent(appointmentId)}/cancel`,
    { method: "POST" },
    token,
  );
}

export function checkInAppointment(appointmentId: string, token: string) {
  return apiRequest<Appointment>(
    `/api/v1/customers/appointments/${encodeURIComponent(appointmentId)}/check-in`,
    { method: "POST" },
    token,
  );
}

export function listAdminAppointmentSlots(serviceId: string, token: string) {
  const query = new URLSearchParams({ service_id: serviceId });
  return apiRequest<AppointmentSlot[]>(
    `/api/v1/admin/appointment-slots?${query}`,
    {},
    token,
  );
}

export function createAdminAppointmentSlot(
  payload: {
    service_id: string;
    starts_at: string;
    ends_at: string;
    capacity: number;
  },
  token: string,
) {
  return apiRequest<AppointmentSlot>(
    "/api/v1/admin/appointment-slots",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}
