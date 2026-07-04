// Admin auth (Zustand). Holds the super-admin token and wires it into the shared
// api client. The token is set on the client SYNCHRONOUSLY (module load + login)
// so the first admin request already carries the header — avoids a token-less
// 401 on mount that would bounce the user back to the login screen.
import { create } from "zustand";
import { api, setAdminToken } from "@veritas/shared";

const TOKEN_KEY = "veritas_admin_token";

interface AuthState {
  token: string | null;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const initial = localStorage.getItem(TOKEN_KEY);
setAdminToken(initial);

export const useAuthStore = create<AuthState>((set) => ({
  token: initial,
  login: async (password: string) => {
    const { token } = await api.adminLogin(password);
    setAdminToken(token);
    localStorage.setItem(TOKEN_KEY, token);
    set({ token });
  },
  logout: () => {
    setAdminToken(null);
    localStorage.removeItem(TOKEN_KEY);
    set({ token: null });
  },
}));
