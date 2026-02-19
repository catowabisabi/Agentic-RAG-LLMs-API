'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../contexts/AuthContext';
import {
  Home,
  Users,
  MessageSquare,
  Database,
  Activity,
  Settings,
  LogOut,
  Bot,
  Brain,
  FlaskConical,
  Wrench,
} from 'lucide-react';
import SystemAlertBanner from './SystemAlertBanner';

const navItems = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Agents', href: '/agents', icon: Users },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'RAG Query', href: '/rag', icon: Database },
  { name: 'Memory', href: '/memory', icon: Brain },
  { name: 'Tools', href: '/tools', icon: Wrench },
  { name: 'Experiment', href: '/experiment', icon: FlaskConical },
  { name: 'WebSocket', href: '/websocket', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
];

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { logout, username, role, isAdmin } = useAuth();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gray-900 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Agentic RAG</h1>
              <p className="text-xs text-gray-400">API Demo</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* User Info + Logout */}
        <div className="p-4 border-t border-gray-700 space-y-2">
          <div className="px-4 py-2 flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isAdmin ? 'bg-yellow-400' : 'bg-green-400'}`} />
            <span className="text-sm text-gray-300">{username}</span>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded ${isAdmin ? 'bg-yellow-900/50 text-yellow-400' : 'bg-gray-700 text-gray-400'}`}>
              {role}
            </span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-gray-300 hover:bg-red-900/50 hover:text-red-300 transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto h-screen flex flex-col">
        <SystemAlertBanner />
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
