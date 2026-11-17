import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

const localStorageData = new Map<string, string>();
const testLocalStorage: Storage = {
  get length() {
    return localStorageData.size;
  },
  clear() {
    localStorageData.clear();
  },
  getItem(key) {
    return localStorageData.get(key) ?? null;
  },
  key(index) {
    return [...localStorageData.keys()][index] ?? null;
  },
  removeItem(key) {
    localStorageData.delete(key);
  },
  setItem(key, value) {
    localStorageData.set(String(key), String(value));
  },
};
vi.stubGlobal("localStorage", testLocalStorage);

beforeEach(() => {
  sessionStorage.clear();
});
