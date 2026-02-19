'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1130';

export type UserRole = 'admin' | 'guest';

interface AuthContextType {
  isAuthenticated: boolean;
  role: UserRole;
  username: string;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState<UserRole>('guest');
  const [username, setUsername] = useState('');

  useEffect(() => {
    // Restore session from localStorage
    const token = localStorage.getItem('auth_token');
    const savedRole = localStorage.getItem('auth_role') as UserRole | null;
    const savedUser = localStorage.getItem('auth_user');
    if (token === 'authenticated' && savedRole) {
      setIsAuthenticated(true);
      setRole(savedRole);
      setUsername(savedUser || '');
    }
  }, []);

  const login = async (usr: string, password: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usr, password }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('auth_token', 'authenticated');
        localStorage.setItem('auth_role', data.role);
        localStorage.setItem('auth_user', data.username);
        setIsAuthenticated(true);
        setRole(data.role as UserRole);
        setUsername(data.username);
        return true;
      }
      return false;
    } catch {
      // Fallback: if API is unreachable, deny login
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_role');
    localStorage.removeItem('auth_user');
    setIsAuthenticated(false);
    setRole('guest');
    setUsername('');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, role, username, isAdmin: role === 'admin', login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
