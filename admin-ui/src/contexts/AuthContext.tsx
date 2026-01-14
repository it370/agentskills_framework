"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User, getStoredUser, setAuth, clearAuth, getAuthToken } from "@/lib/auth";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Initialize auth state from localStorage
  useEffect(() => {
    const storedToken = getAuthToken();
    const storedUser = getStoredUser();
    
    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(storedUser);
      // Verify token is still valid
      verifyToken(storedToken).catch(() => {
        clearAuth();
        setToken(null);
        setUser(null);
      });
    }
    
    setLoading(false);
  }, []);

  async function verifyToken(token: string): Promise<void> {
    const res = await fetch(`${API_BASE}/auth/verify-token`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    
    if (!res.ok) {
      throw new Error("Token verification failed");
    }
  }

  async function login(username: string, password: string): Promise<void> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const error = await res.json();
      
      // Handle FastAPI validation errors (422)
      if (Array.isArray(error.detail)) {
        const messages = error.detail.map((err: any) => err.msg || err.message).join(", ");
        throw new Error(messages || "Validation failed");
      }
      
      // Handle string error messages
      throw new Error(error.detail || "Login failed");
    }

    const data = await res.json();
    setAuth(data.access_token, data.user);
    setToken(data.access_token);
    setUser(data.user);
    router.push("/");
  }

  async function register(username: string, email: string, password: string): Promise<void> {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, email, password }),
    });

    if (!res.ok) {
      const error = await res.json();
      
      // Handle FastAPI validation errors (422)
      if (Array.isArray(error.detail)) {
        const messages = error.detail.map((err: any) => err.msg || err.message).join(", ");
        throw new Error(messages || "Validation failed");
      }
      
      // Handle string error messages
      throw new Error(error.detail || "Registration failed");
    }

    const data = await res.json();
    setAuth(data.access_token, data.user);
    setToken(data.access_token);
    setUser(data.user);
    router.push("/");
  }

  async function logout(): Promise<void> {
    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (error) {
        console.error("Logout error:", error);
      }
    }

    clearAuth();
    setToken(null);
    setUser(null);
    router.push("/login");
  }

  async function refreshUser(): Promise<void> {
    if (!token) return;

    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) throw new Error("Failed to refresh user");

      const userData = await res.json();
      setUser(userData);
      setAuth(token, userData);
    } catch (error) {
      console.error("Failed to refresh user:", error);
      await logout();
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
