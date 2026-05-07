import { createContext, useContext, useEffect, useState } from "react";

import { apiRequest, setActiveAccountId, setAuthToken } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("ezecraft_token"));
  const [activeAccountId, setActiveAccountIdState] = useState(() => localStorage.getItem("ezecraft_active_account_id"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthToken(token);
    setActiveAccountId(activeAccountId);
    if (!token) {
      setLoading(false);
      return;
    }

    apiRequest("/auth/me")
      .then((data) => {
        setUser(data);
        if (data.role === "platform_admin") {
          const nextAccountId = activeAccountId || String(data.active_account_id || data.account_id || "");
          if (nextAccountId) {
            localStorage.setItem("ezecraft_active_account_id", nextAccountId);
            setActiveAccountId(nextAccountId);
            setActiveAccountIdState(nextAccountId);
          }
        }
      })
      .catch(() => {
        localStorage.removeItem("ezecraft_token");
        localStorage.removeItem("ezecraft_active_account_id");
        setAuthToken(null);
        setActiveAccountId(null);
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [token, activeAccountId]);

  const hasSubscription =
    user?.role === "platform_admin" ||
    !!(user?.account?.active_subscription);

  const value = {
    token,
    user,
    activeAccountId,
    hasSubscription,
    loading,
    async login(email, password) {
      const data = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      localStorage.setItem("ezecraft_token", data.access_token);
      setAuthToken(data.access_token);
      setToken(data.access_token);
    },
    loginWithToken(token) {
      localStorage.setItem("ezecraft_token", token);
      setAuthToken(token);
      setToken(token);
    },
    logout() {
      localStorage.removeItem("ezecraft_token");
      localStorage.removeItem("ezecraft_active_account_id");
      setAuthToken(null);
      setActiveAccountId(null);
      setToken(null);
      setActiveAccountIdState(null);
      setUser(null);
    },
    switchAccount(accountId) {
      const nextValue = accountId ? String(accountId) : null;
      if (nextValue) {
        localStorage.setItem("ezecraft_active_account_id", nextValue);
      } else {
        localStorage.removeItem("ezecraft_active_account_id");
      }
      setActiveAccountId(nextValue);
      setActiveAccountIdState(nextValue);
    }
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
