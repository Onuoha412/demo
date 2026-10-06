import { create } from "zustand";

import type { User } from "../types/api";

type AuthState = {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
};

const TOKEN_KEY = "queueless.token";
const USER_KEY = "queueless.user";

const initialToken = localStorage.getItem(TOKEN_KEY);
const initialUser = localStorage.getItem(USER_KEY);

export const useAuthStore = create<AuthState>((set) => ({
  token: initialToken,
  user: initialUser ? (JSON.parse(initialUser) as User) : null,
  setAuth: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null });
  },
}));
