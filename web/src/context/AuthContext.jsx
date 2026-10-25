import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "../lib/api";
import { firebaseEnabled, signInWithFirebase, signOutOfFirebase } from "../lib/firebase";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  const clear = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setMe(null);
  }, []);

  const loadMe = useCallback(async (activeToken) => {
    const profile = await api("/auth/me", { token: activeToken });
    setMe(profile);
    return profile;
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    loadMe(token)
      .catch(() => {
        if (!cancelled) clear();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, loadMe, clear]);

  const signInWithDevToken = useCallback(
    async (uidOrToken) => {
      const value = String(uidOrToken || "").trim();
      if (!value) throw new Error("Enter a user id or development token.");
      const devToken = value.startsWith("dev:") ? value : `dev:${value}`;
      const profile = await api("/auth/me", { token: devToken });
      setToken(devToken);
      setTokenState(devToken);
      setMe(profile);
      return profile;
    },
    []
  );

  const signInWithEmail = useCallback(
    async (email, password) => {
      if (!firebaseEnabled) throw new Error("Firebase sign-in is not configured.");
      const idToken = await signInWithFirebase(email, password);
      const profile = await api("/auth/me", { token: idToken });
      setToken(idToken);
      setTokenState(idToken);
      setMe(profile);
      return profile;
    },
    []
  );

  const signOut = useCallback(async () => {
    await signOutOfFirebase();
    clear();
  }, [clear]);

  const refresh = useCallback(async () => {
    if (!token) return null;
    return loadMe(token);
  }, [token, loadMe]);

  const value = useMemo(
    () => ({
      token,
      me,
      loading,
      firebaseEnabled,
      signInWithDevToken,
      signInWithEmail,
      signOut,
      refresh,
      isAdmin: me?.role === "admin",
      isTrainer: me?.role === "trainer",
      isStudent: me?.role === "student",
      isStaff: me?.role === "admin" || me?.role === "trainer",
    }),
    [
      token,
      me,
      loading,
      signInWithDevToken,
      signInWithEmail,
      signOut,
      refresh,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
