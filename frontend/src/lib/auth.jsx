import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setToken, getToken } from "./api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setToken(null); setUser(null);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    refresh();
    // handle Emergent Google OAuth redirect
    const hash = window.location.hash;
    if (hash.startsWith("#session_id=")) {
      const sid = hash.split("=")[1];
      window.location.hash = "";
      api.post("/auth/google", { session_id: sid }).then(({ data }) => {
        setToken(data.token); setUser(data.user);
      }).catch(() => {});
    }
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.token); setUser(data.user);
    return data.user;
  };
  const signup = async (email, password, name) => {
    const { data } = await api.post("/auth/signup", { email, password, name });
    setToken(data.token); setUser(data.user);
    return data.user;
  };
  const loginWithGoogle = () => {
    const redirect = encodeURIComponent(window.location.origin + "/auth/callback");
    window.location.href = `https://auth.emergentagent.com/?redirect=${redirect}`;
  };
  const logout = () => { setToken(null); setUser(null); };

  return (
    <AuthCtx.Provider value={{ user, loading, login, signup, logout, loginWithGoogle, refresh, setUser }}>
      {children}
    </AuthCtx.Provider>
  );
};

export const useAuth = () => useContext(AuthCtx);
