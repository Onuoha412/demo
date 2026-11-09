import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  bookAppointment,
  cancelAppointment,
  checkInAppointment,
  listAvailableAppointmentSlots,
  listCustomerAppointments,
} from "../../services/appointments";
import { useAuthStore } from "../../store/authStore";

function dateTime(value: string) {
  return new Date(value).toLocaleString();
}

export function AppointmentsPage() {
  const { serviceId } = useParams();
  const token = useAuthStore((state) => state.token)!;
  const client = useQueryClient();
  const [now, setNow] = useState(0);
  useEffect(() => {
    const updateTime = () => setNow(Date.now());
    updateTime();
    const interval = window.setInterval(updateTime, 30_000);
    return () => window.clearInterval(interval);
  }, []);
  const appointments = useQuery({
    queryKey: ["appointments"],
    queryFn: () => listCustomerAppointments(token),
  });
  const slots = useQuery({
    queryKey: ["appointment-slots", serviceId],
    queryFn: () => listAvailableAppointmentSlots(serviceId!, token),
    enabled: Boolean(serviceId),
  });
  const action = useMutation({
    mutationFn: ({
      kind,
      id,
    }: {
      kind: "book" | "cancel" | "check-in";
      id: string;
    }) =>
      kind === "book"
        ? bookAppointment(id, token)
        : kind === "cancel"
          ? cancelAppointment(id, token)
          : checkInAppointment(id, token),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["appointments"] });
      void client.invalidateQueries({ queryKey: ["appointment-slots"] });
    },
  });

  return (
    <PageContainer className="py-10">
      <h1 className="text-4xl font-black text-ink">
        {serviceId ? "Book an appointment" : "My appointments"}
      </h1>

      {serviceId && (
        <section className="mt-6 rounded-2xl bg-white p-5">
          <h2 className="text-xl font-bold">Available times</h2>
          {slots.isLoading && <LoadingState label="Loading appointment times..." />}
          {slots.isError && (
            <ErrorState
              message="Appointment times could not be loaded."
              onRetry={() => void slots.refetch()}
            />
          )}
          {slots.data?.length === 0 && (
            <EmptyState
              title="No available appointments"
              message="There are no open appointment times for this service."
            />
          )}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {(slots.data ?? []).map((slot) => (
              <article key={slot.id} className="rounded-xl border border-ink/10 p-4">
                <p className="font-semibold">{dateTime(slot.starts_at)}</p>
                <p className="mt-1 text-sm text-ink/60">
                  {slot.capacity - slot.booked_count} place
                  {slot.capacity - slot.booked_count === 1 ? "" : "s"} available
                </p>
                <button
                  className="mt-3 rounded-full bg-ink px-4 py-2 text-sm text-white"
                  disabled={action.isPending}
                  onClick={() => action.mutate({ kind: "book", id: slot.id })}
                >
                  Book this time
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-2xl font-bold">Your bookings</h2>
        {appointments.isLoading && <LoadingState label="Loading appointments..." />}
        {appointments.isError && (
          <ErrorState
            message="Your appointments could not be loaded."
            onRetry={() => void appointments.refetch()}
          />
        )}
        {appointments.data?.length === 0 && (
          <EmptyState
            title="No appointments yet"
            message="Book an available time from a service page."
          />
        )}
        <div className="mt-4 space-y-3">
          {(appointments.data ?? []).map((appointment) => {
            const start = new Date(appointment.starts_at).getTime();
            const end = new Date(appointment.ends_at).getTime();
            const canCheckIn =
              appointment.status === "booked" &&
              now >= start - 15 * 60_000 &&
              now <= end;
            return (
              <article
                key={appointment.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-white p-5"
              >
                <div>
                  <h3 className="font-bold">{appointment.service_name}</h3>
                  <p className="mt-1 text-sm text-ink/60">
                    {dateTime(appointment.starts_at)} · {appointment.status.replaceAll("_", " ")}
                  </p>
                </div>
                <div className="flex gap-2">
                  {canCheckIn && (
                    <button
                      className="rounded-full bg-emerald-700 px-4 py-2 text-sm text-white"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ kind: "check-in", id: appointment.id })
                      }
                    >
                      Check in
                    </button>
                  )}
                  {appointment.status === "booked" && now > 0 && start > now && (
                    <button
                      className="rounded-full border border-ink/20 px-4 py-2 text-sm"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({ kind: "cancel", id: appointment.id })
                      }
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>
      {action.isError && (
        <div className="mt-4" role="alert">
          <ErrorState message="The appointment action could not be completed. Please refresh and try again." />
        </div>
      )}
      <Link className="mt-6 inline-block font-semibold text-emerald-800" to="/services">
        Browse services
      </Link>
    </PageContainer>
  );
}
