'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type UserRole = 'admin' | 'guest';

interface AuthContextType {
  isAuthenticated: boolean;
  role: UserRole;
  username: string;
  isAdmin: boolean;
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Credentials map: username -> { password, role }
const USERS: Record<string, { password: string; role: UserRole }> = {
  admin: { password: 'admin', role: 'admin' },
  guest: { password: 'beourguest', role: 'guest' },
};

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

  const login = (usr: string, password: string): boolean => {
    const user = USERS[usr];
    if (user && user.password === password) {
      localStorage.setItem('auth_token', 'authenticated');
      localStorage.setItem('auth_role', user.role);
      localStorage.setItem('auth_user', usr);
      setIsAuthenticated(true);
      setRole(user.role);
      setUsername(usr);
      return true;
    }
    return false;
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
