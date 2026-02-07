'use client';

import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { WebSocketProvider } from '../contexts/WebSocketContext';
import Layout from '../components/Layout';
import LoginForm from '../components/LoginForm';
import '../styles/globals.css';

function AuthenticatedApp({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return (
    <WebSocketProvider>
      <Layout>{children}</Layout>
    </WebSocketProvider>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <AuthenticatedApp>{children}</AuthenticatedApp>
        </AuthProvider>
      </body>
    </html>
  );
}
