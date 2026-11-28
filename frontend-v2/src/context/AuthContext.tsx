import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "../api/auth";
import { setUnauthorizedHandler } from "../api/client";
import type { AuthUser, LoginRequest, RegisterRequest } from "../types/api";

interface AuthContextValue {
  user: AuthUser | null;
  isCheckingSession: boolean;
  sessionNotice: string | null;
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearSessionNotice: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setSessionNotice(
        "Sesi login Anda telah berakhir. Silakan masuk kembali untuk melanjutkan.",
      );
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let active = true;
    const restoreSession = async () => {
      try {
        const resp = await getCurrentUser();
        if (active) {
          setUser(resp.data);
        }
      } catch {
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setIsCheckingSession(false);
        }
      }
    };
    void restoreSession();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (payload: LoginRequest) => {
    const resp = await loginUser(payload);
    setSessionNotice(null);
    setUser(resp.data);
  }, []);

  const register = useCallback(async (payload: RegisterRequest) => {
    const resp = await registerUser(payload);
    setSessionNotice(null);
    setUser(resp.data);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } finally {
      setSessionNotice(null);
      setUser(null);
    }
  }, []);

  const clearSessionNotice = useCallback(() => {
    setSessionNotice(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isCheckingSession,
      sessionNotice,
      login,
      register,
      logout,
      clearSessionNotice,
    }),
    [
      user,
      isCheckingSession,
      sessionNotice,
      login,
      register,
      logout,
      clearSessionNotice,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth harus digunakan di dalam AuthProvider.");
  }
  return ctx;
}
