"use client";

import "./globals.css";
import { ReduxProvider } from "@/contexts/ReduxProvider";
import { RunProvider } from "@/contexts/RunContext";
import { AuthProvider } from "@/contexts/AuthContext";

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
              {children}
            </RunProvider>
          </AuthProvider>
        </ReduxProvider>
      </body>
    </html>
  );
}
