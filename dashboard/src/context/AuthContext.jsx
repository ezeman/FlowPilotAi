import { createContext, useContext, useEffect, useState } from "react";

import { apiRequest, setActiveAccountId, setAuthToken } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("flowpilot_token"));
  const [activeAccountId, setActiveAccountIdState] = useState(() => localStorage.getItem("flowpilot_active_account_id"));
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
            localStorage.setItem("flowpilot_active_account_id", nextAccountId);
            setActiveAccountId(nextAccountId);
            setActiveAccountIdState(nextAccountId);
          }
        }
      })
      .catch(() => {
        localStorage.removeItem("flowpilot_token");
        localStorage.removeItem("flowpilot_active_account_id");
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
      localStorage.setItem("flowpilot_token", data.access_token);
      setAuthToken(data.access_token);
      setToken(data.access_token);
    },
    loginWithToken(token) {
      localStorage.setItem("flowpilot_token", token);
      setAuthToken(token);
      setToken(token);
    },
    logout() {
      localStorage.removeItem("flowpilot_token");
      localStorage.removeItem("flowpilot_active_account_id");
      setAuthToken(null);
      setActiveAccountId(null);
      setToken(null);
      setActiveAccountIdState(null);
      setUser(null);
    },
    switchAccount(accountId) {
      const nextValue = accountId ? String(accountId) : null;
      if (nextValue) {
        localStorage.setItem("flowpilot_active_account_id", nextValue);
      } else {
        localStorage.removeItem("flowpilot_active_account_id");
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
