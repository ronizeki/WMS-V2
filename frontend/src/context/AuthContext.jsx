import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import api, { setUnauthorizedHandler, tokenStore } from '../lib/api';

const AuthContext = createContext(null);

const USER_CACHE_KEY = 'sp.user';

function readCachedUser() {
  try {
    const raw = window.localStorage.getItem(USER_CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readCachedUser);
  const [tenant, setTenant] = useState(user?.tenant || null);
  const [loading, setLoading] = useState(true);
  const bootstrapped = useRef(false);

  const persistUser = useCallback((next) => {
    setUser(next);
    try {
      if (next) window.localStorage.setItem(USER_CACHE_KEY, JSON.stringify(next));
      else window.localStorage.removeItem(USER_CACHE_KEY);
    } catch (e) {
      /* ignore */
    }
  }, []);

  const clearSession = useCallback(() => {
    tokenStore.clear();
    persistUser(null);
    setTenant(null);
  }, [persistUser]);

  const loadMe = useCallback(async () => {
    const me = await api.get('/auth/me');
    persistUser(me);
    setTenant(me.tenant || null);
    return me;
  }, [persistUser]);

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const login = useCallback(
    async ({ email, password, tenantCode }) => {
      const result = await api.post(
        '/auth/login',
        { email, password, tenant_code: tenantCode || undefined },
        { auth: false }
      );
      tokenStore.set({ accessToken: result.access_token, refreshToken: result.refresh_token });
      if (result.user?.tenant_id) tokenStore.set({ tenantId: result.user.tenant_id });
      persistUser(result.user);
      setTenant(result.user?.tenant || null);
      try {
        const me = await loadMe();
        return me;
      } catch (e) {
        return result.user;
      }
    },
    [persistUser, loadMe]
  );

  // Restore the session on first mount.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    setUnauthorizedHandler(() => {
      clearSession();
    });

    const token = tokenStore.getAccess();
    if (!token) {
      setLoading(false);
      return;
    }
    loadMe()
      .catch(async () => {
        const refresh = tokenStore.getRefresh();
        if (!refresh) {
          clearSession();
          return;
        }
        try {
          const refreshed = await api.post('/auth/refresh', { refresh_token: refresh }, { auth: false });
          tokenStore.set({ accessToken: refreshed.access_token });
          await loadMe();
        } catch (e) {
          clearSession();
        }
      })
      .finally(() => setLoading(false));
  }, [clearSession, loadMe]);

  const selectTenant = useCallback(
    async (tenantId) => {
      tokenStore.set({ tenantId: tenantId || '' });
      setTenant(null);
      await loadMe();
    },
    [loadMe]
  );

  const value = useMemo(
    () => {
      const permissions = user?.permissions || [];
      return {
        user,
        tenant,
        permissions,
        loading,
        isAuthenticated: Boolean(user),
        isPlatformAdmin: Boolean(user?.is_platform_admin),
        hasPermission: (code) => permissions.includes(code),
        hasAnyPermission: (...codes) => codes.some((c) => permissions.includes(c)),
        login,
        logout,
        selectTenant,
        async refresh() {
          const refreshToken = tokenStore.getRefresh();
          if (!refreshToken) return;
          const refreshed = await api.post('/auth/refresh', { refresh_token: refreshToken }, { auth: false });
          tokenStore.set({ accessToken: refreshed.access_token });
          await loadMe();
        },
        activeTenantId: tokenStore.getTenant(),
      };
    },
    [user, tenant, loading, login, logout, selectTenant, loadMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}

export default AuthContext;
