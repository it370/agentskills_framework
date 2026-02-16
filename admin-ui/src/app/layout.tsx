"use client";

import "./globals.css";
import { ReduxProvider } from "@/contexts/ReduxProvider";
import { RunProvider } from "@/contexts/RunContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { ToastProvider } from "@/contexts/ToastContext";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ReduxProvider>
          <AuthProvider>
            <RunProvider>
              <ToastProvider>
                {children}
              </ToastProvider>
            </RunProvider>
          </AuthProvider>
        </ReduxProvider>
      </body>
    </html>
  );
}
