import { createContext, useContext, useEffect, useState } from "react";

import { apiRequest, setAuthToken } from "../services/api";
import { isPlatformOwner } from "../utils/roles";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("ezecraft_token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthToken(token);
    if (!token) {
      setLoading(false);
      return;
    }

    apiRequest("/auth/me")
      .then((data) => setUser(data))
      .catch(() => {
        localStorage.removeItem("ezecraft_token");
        setAuthToken(null);
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const hasSubscription =
    isPlatformOwner(user) ||
    !!(user?.account?.active_subscription);

  const value = {
    token,
    user,
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
      setAuthToken(null);
      setToken(null);
      setUser(null);
    }
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
