import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import { PageContainer } from "../../components/common/PageContainer";
import {
  createAdminAppointmentSlot,
  listAdminAppointmentSlots,
} from "../../services/appointments";
import { useAuthStore } from "../../store/authStore";

function localInputToIso(value: string) {
  return new Date(value).toISOString();
}

export function AppointmentSlotsPage() {
  const { serviceId = "" } = useParams();
  const token = useAuthStore((state) => state.token)!;
  const client = useQueryClient();
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [capacity, setCapacity] = useState("1");
  const slots = useQuery({
    queryKey: ["admin-appointment-slots", serviceId],
    queryFn: () => listAdminAppointmentSlots(serviceId, token),
  });
  const create = useMutation({
    mutationFn: () =>
      createAdminAppointmentSlot(
        {
          service_id: serviceId,
          starts_at: localInputToIso(startsAt),
          ends_at: localInputToIso(endsAt),
          capacity: Number(capacity),
        },
        token,
      ),
    onSuccess: () => {
      setStartsAt("");
      setEndsAt("");
      void client.invalidateQueries({
        queryKey: ["admin-appointment-slots", serviceId],
      });
    },
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    create.mutate();
  };

  return (
    <PageContainer className="py-10">
      <h1 className="text-4xl font-black">Appointment schedule</h1>
      <form className="mt-6 grid gap-4 rounded-2xl bg-white p-5 sm:grid-cols-4" onSubmit={submit}>
        <label className="grid gap-1 text-sm font-semibold">
          Starts at
          <input
            required
            type="datetime-local"
            value={startsAt}
            onChange={(event) => setStartsAt(event.target.value)}
            className="rounded-lg border p-2"
          />
        </label>
        <label className="grid gap-1 text-sm font-semibold">
          Ends at
          <input
            required
            type="datetime-local"
            min={startsAt}
            value={endsAt}
            onChange={(event) => setEndsAt(event.target.value)}
            className="rounded-lg border p-2"
          />
        </label>
        <label className="grid gap-1 text-sm font-semibold">
          Booking capacity
          <input
            required
            min="1"
            max="500"
            type="number"
            value={capacity}
            onChange={(event) => setCapacity(event.target.value)}
            className="rounded-lg border p-2"
          />
        </label>
        <button
          className="self-end rounded-full bg-ink px-5 py-2 text-white"
          type="submit"
          disabled={create.isPending}
        >
          {create.isPending ? "Saving..." : "Add appointment time"}
        </button>
      </form>
      {create.isError && (
        <div className="mt-4" role="alert">
          <ErrorState message="The appointment time could not be saved. Check for a duplicate time or invalid date." />
        </div>
      )}
      <div className="mt-8">
        {slots.isLoading && <LoadingState label="Loading schedule..." />}
        {slots.isError && (
          <ErrorState
            message="The appointment schedule could not be loaded."
            onRetry={() => void slots.refetch()}
          />
        )}
        <div className="space-y-3">
          {(slots.data ?? []).map((slot) => (
            <article key={slot.id} className="rounded-xl bg-white p-4">
              <p className="font-semibold">
                {new Date(slot.starts_at).toLocaleString()} –{" "}
                {new Date(slot.ends_at).toLocaleTimeString()}
              </p>
              <p className="text-sm text-ink/60">
                {slot.booked_count} / {slot.capacity} booked ·{" "}
                {slot.is_open ? "open" : "closed"}
              </p>
            </article>
          ))}
        </div>
      </div>
    </PageContainer>
  );
}
