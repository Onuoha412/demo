import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ErrorState } from "../../components/common/ErrorState";
import { PageContainer } from "../../components/common/PageContainer";
import { PasswordInput } from "../../components/common/PasswordInput";
import { changePassword, updateProfile } from "../../services/auth";
import { useAuthStore } from "../../store/authStore";
import { ApiError } from "../../services/api";

export function ProfilePage() {
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const setAuth = useAuthStore((state) => state.setAuth);
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordValidation, setPasswordValidation] = useState("");
  const profile = useMutation({
    mutationFn: () => updateProfile(fullName.trim()),
    onSuccess: (updatedUser) => {
      if (token) setAuth(updatedUser, token);
    },
  });
  const password = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
  });

  const submitPassword = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordValidation("The new passwords do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordValidation("Choose a new password different from your current one.");
      return;
    }
    setPasswordValidation("");
    password.mutate({
      current_password: currentPassword,
      new_password: newPassword,
    });
  };

  return (
    <PageContainer className="max-w-2xl py-10">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">
        Account settings
      </p>
      <h1 className="mt-2 text-4xl font-black text-ink">Your profile</h1>
      <p className="mt-3 text-ink/65">
        Keep your account details up to date and protect your sign-in.
      </p>

      <form
        className="mt-6 rounded-2xl border border-ink/10 bg-white p-6"
        onSubmit={(event) => {
          event.preventDefault();
          profile.mutate();
        }}
      >
        <h2 className="text-xl font-black text-ink">Personal details</h2>
        <label className="mt-5 block text-sm font-semibold text-ink" htmlFor="profile-name">
          Full name
          <input
            autoComplete="name"
            className="mt-1 w-full rounded-xl border border-ink/15 bg-white px-3.5 py-3"
            id="profile-name"
            maxLength={160}
            minLength={2}
            onChange={(event) => setFullName(event.target.value)}
            required
            value={fullName}
          />
        </label>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-ink/60">Email</p>
            <p className="mt-1 break-all font-medium text-ink">{user?.email}</p>
            <p className="mt-1 text-xs text-ink/50">Contact support if you need to change it.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-ink/60">Account role</p>
            <p className="mt-1 font-medium capitalize text-ink">
              {user?.role.replace("_", " ")}
            </p>
          </div>
        </div>
        {profile.error instanceof ApiError && (
          <p className="mt-4 text-sm text-red-700" role="alert">
            {profile.error.detail}
          </p>
        )}
        {profile.isSuccess && (
          <p className="mt-4 text-sm text-emerald-800" role="status">
            Your profile has been updated.
          </p>
        )}
        <button
          className="mt-5 rounded-full bg-ink px-5 py-3 text-sm font-bold text-white transition hover:bg-emerald-900 disabled:opacity-60"
          disabled={
            profile.isPending ||
            !fullName.trim() ||
            fullName.trim() === user?.full_name
          }
          type="submit"
        >
          {profile.isPending ? "Saving..." : "Save profile"}
        </button>
      </form>

      <form
        className="mt-5 rounded-2xl border border-ink/10 bg-white p-6"
        onSubmit={submitPassword}
      >
        <h2 className="text-xl font-black text-ink">Change password</h2>
        <p className="mt-1 text-sm text-ink/60">
          Changing your password signs out your other active sessions.
        </p>
        <label className="mt-5 block text-sm font-semibold text-ink" htmlFor="current-password">
          Current password
          <PasswordInput
            autoComplete="current-password"
            className="mt-1 w-full rounded-xl border border-ink/15 bg-white px-3.5 py-3"
            id="current-password"
            maxLength={128}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            value={currentPassword}
          />
        </label>
        <label className="mt-4 block text-sm font-semibold text-ink" htmlFor="new-password">
          New password
          <PasswordInput
            autoComplete="new-password"
            className="mt-1 w-full rounded-xl border border-ink/15 bg-white px-3.5 py-3"
            id="new-password"
            minLength={8}
            maxLength={128}
            onChange={(event) => setNewPassword(event.target.value)}
            required
            value={newPassword}
          />
        </label>
        <label className="mt-4 block text-sm font-semibold text-ink" htmlFor="confirm-password">
          Confirm new password
          <PasswordInput
            autoComplete="new-password"
            className="mt-1 w-full rounded-xl border border-ink/15 bg-white px-3.5 py-3"
            id="confirm-password"
            minLength={8}
            maxLength={128}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            value={confirmPassword}
          />
        </label>
        {(passwordValidation || password.error) && (
          <p className="mt-4 text-sm text-red-700" role="alert">
            {passwordValidation ||
              (password.error instanceof ApiError
                ? password.error.detail
                : "Unable to change your password. Please try again.")}
          </p>
        )}
        {password.isSuccess && (
          <p className="mt-4 text-sm text-emerald-800" role="status">
            {password.data.message}
          </p>
        )}
        <button
          className="mt-5 rounded-full bg-ink px-5 py-3 text-sm font-bold text-white transition hover:bg-emerald-900 disabled:opacity-60"
          disabled={
            password.isPending ||
            !currentPassword ||
            newPassword.length < 8 ||
            confirmPassword.length < 8
          }
          type="submit"
        >
          {password.isPending ? "Updating..." : "Update password"}
        </button>
      </form>
      {profile.error && !(profile.error instanceof ApiError) && (
        <div className="mt-5">
          <ErrorState message="Unable to update your profile. Please try again." />
        </div>
      )}
    </PageContainer>
  );
}
