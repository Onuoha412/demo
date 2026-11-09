import { create } from "zustand";

import type { User } from "../types/api";

type AuthState = {
  token: string | null;
  user: User | null;
  ready: boolean;
  setAuth: (user: User, token: string, remember?: boolean) => void;
  setReady: () => void;
  logout: () => void;
};

const TOKEN_KEY = "queueless.session";
const REMEMBERED_TOKEN_KEY = "queueless.remembered";

function clearLegacyCredentials(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem("queueless.token");
  localStorage.removeItem("queueless.user");
}

function getStoredToken(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  return (
    sessionStorage.getItem(TOKEN_KEY) ??
    (typeof localStorage === "undefined"
      ? null
      : localStorage.getItem(REMEMBERED_TOKEN_KEY))
  );
}

clearLegacyCredentials();

export const useAuthStore = create<AuthState>((set) => ({
  token: getStoredToken(),
  user: null,
  ready: false,
  setAuth: (user, token, remember = false) => {
    if (typeof sessionStorage !== "undefined") {
      if (remember) {
        sessionStorage.removeItem(TOKEN_KEY);
      } else {
        sessionStorage.setItem(TOKEN_KEY, token);
      }
    }
    if (typeof localStorage !== "undefined") {
      if (remember) {
        localStorage.setItem(REMEMBERED_TOKEN_KEY, token);
      } else {
        localStorage.removeItem(REMEMBERED_TOKEN_KEY);
      }
    }
    set({ token, user, ready: true });
  },
  setReady: () => set({ ready: true }),
  logout: () => {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(TOKEN_KEY);
    }
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(REMEMBERED_TOKEN_KEY);
    }
    set({ token: null, user: null, ready: true });
  },
}));
