'use client';

/**
 * lib/auth.tsx
 * Auth context — JWT stored in localStorage.
 * Handles token refresh events and role-based access.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api, setToken, getToken, User, AUTH_EXPIRED_EVENT } from './api';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: User['role'][]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(async () => {
    try {
      if (getToken()) await api.auth.logout();
    } catch {}
    if (typeof window !== 'undefined') localStorage.removeItem('sentinel_token');
    setToken(null);
    setTokenState(null);
    setUser(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }, []);

  // Initialize from localStorage
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window === 'undefined') {
        setIsLoading(false);
        return;
      }
      
      const storedToken = localStorage.getItem('sentinel_token');
      if (storedToken) {
        setToken(storedToken);
        try {
          // DEMO MOCK: Skip backend API for session check
          const dummyUser = {
            user_id: 1,
            username: "admin",
            email: "admin@sentinelai.local",
            role: "ADMIN",
            station_id: null,
            is_active: true
          } as any;
          setUser(dummyUser);
          setTokenState(storedToken);
        } catch (_) {
          localStorage.removeItem('sentinel_token');
          setToken(null);
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  // Listen for auth expiry events
  useEffect(() => {
    const handler = () => logout();
    window.addEventListener(AUTH_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
  }, [logout]);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      // DEMO MOCK: Skip backend API entirely
      const demoToken = "demo-mock-token-123";
      const demoUser = {
        user_id: 1,
        username: "admin",
        email: "admin@sentinelai.local",
        role: "ADMIN",
        station_id: null,
        is_active: true
      } as any;
      
      if (typeof window !== 'undefined') localStorage.setItem('sentinel_token', demoToken);
      setToken(demoToken);
      setTokenState(demoToken);
      setUser(demoUser);
    } finally {
      setIsLoading(false);
    }
  };

  const hasRole = (...roles: User['role'][]) => {
    if (!user) return false;
    if (user.role === 'ADMIN') return true;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated: !!user, isLoading, login, logout, hasRole }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
