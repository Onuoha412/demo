import type { User } from "../types/api";

export function roleHomePath(role: User["role"]): string {
  switch (role) {
    case "staff":
      return "/staff/dashboard";
    case "admin":
      return "/admin/dashboard";
    case "customer":
      return "/";
  }
}

export function roleLoginPath(role: User["role"]): string {
  switch (role) {
    case "staff":
      return "/staff/login";
    case "admin":
      return "/admin/login";
    case "customer":
      return "/login";
  }
}
