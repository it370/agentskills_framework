"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import WorkspaceSwitcher from "./WorkspaceSwitcher";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { toggleSidebarCollapsed } from "@/store/slices/uiSlice";

export default function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const { user } = useAuth();
  const dispatch = useAppDispatch();
  const sidebarCollapsed = useAppSelector((s) => s.ui.sidebarCollapsed);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  const navItems = [
    { name: "Runs", path: "/", icon: RocketIcon },
    { name: "Skills", path: "/skills", icon: BuilderIcon },
    { name: "Logs", path: "/logs", icon: TerminalIcon },
    { name: "Workflows", path: "/workflows", icon: WorkflowIcon },
  ];
  if (user?.is_admin) {
    navItems.push({ name: "Run Manager", path: "/run-manager", icon: DatabaseIcon });
    navItems.push({ name: "System Errors", path: "/admin/system-errors", icon: AlertIcon });
  }
  if (user?.username === "system") {
    navItems.push({ name: "LLM Models", path: "/admin/llm-models", icon: SettingsIcon });
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile drawer */}
      {mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-72 bg-gray-900 text-white flex flex-col shadow-xl">
            <SidebarContent
              pathname={pathname}
              navItems={navItems}
              collapsed={false}
              onNavigate={() => setMobileDrawerOpen(false)}
              onToggleCollapse={undefined}
            />
          </aside>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside
        className={`hidden lg:flex bg-gray-900 text-white flex-col transition-[width] duration-200 ${
          sidebarCollapsed ? "w-20" : "w-64"
        }`}
      >
        <SidebarContent
          pathname={pathname}
          navItems={navItems}
          collapsed={sidebarCollapsed}
          onNavigate={undefined}
          onToggleCollapse={() => dispatch(toggleSidebarCollapsed())}
        />
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 px-4 border-b border-gray-200 bg-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="lg:hidden inline-flex items-center justify-center rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              onClick={() => setMobileDrawerOpen(true)}
              aria-label="Open navigation menu"
            >
              <HamburgerIcon className="h-5 w-5" />
            </button>
            <WorkspaceSwitcher />
          </div>
        </header>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({
  pathname,
  navItems,
  collapsed,
  onNavigate,
  onToggleCollapse,
}: {
  pathname: string;
  navItems: Array<{ name: string; path: string; icon: (p: { className?: string }) => ReactNode }>;
  collapsed: boolean;
  onNavigate?: () => void;
  onToggleCollapse?: () => void;
}) {
  return (
    <>
      <div className="p-4 border-b border-gray-800 flex items-center justify-between gap-2">
        <div className={`min-w-0 ${collapsed ? "w-full flex justify-center" : ""}`}>
          <div className={`flex items-center gap-2 ${collapsed ? "justify-center" : ""}`}>
            {/* {collapsed && <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold">
              A
            </div>} */}
            {!collapsed && (
              <div className="min-w-0">
                <h1 className="text-base font-bold leading-tight truncate">Agent Skills</h1>
                <p className="text-xs text-gray-400 leading-tight truncate">Orchestrator v{process.env.NEXT_PUBLIC_APP_VERSION}</p>
              </div>
            )}
          </div>
        </div>
        {onToggleCollapse && (
          <button
            type="button"
            className="hidden lg:inline-flex items-center justify-center rounded-md p-2 text-gray-300 hover:bg-gray-800 hover:text-white"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand" : "Collapse"}
          >
            <CollapseIcon className={`h-5 w-5 ${collapsed ? "rotate-180" : ""}`} />
          </button>
        )}
      </div>

      <nav className="flex-1 p-3">
        <ul className="space-y-2">
          {navItems.map((item) => {
            const isActive =
              pathname === item.path || (item.path !== "/" && pathname.startsWith(item.path));
            return (
              <li key={item.path}>
                <Link
                  href={item.path}
                  onClick={onNavigate}
                  title={collapsed ? item.name : undefined}
                  className={`flex items-center gap-3 rounded-lg transition-colors ${
                    collapsed ? "px-3 py-3 justify-center" : "px-4 py-3"
                  } ${
                    isActive
                      ? "bg-gray-800 text-white"
                      : "text-gray-400 hover:bg-gray-800 hover:text-white"
                  }`}
                >
                  <item.icon className="w-5 h-5" />
                  {!collapsed && <span className="font-medium">{item.name}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-3 border-t border-gray-800">
        <UserMenu collapsed={collapsed} />
      </div>
    </>
  );
}

function RocketIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 10V3L4 14h7v7l9-11h-7z"
      />
    </svg>
  );
}

function TerminalIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}

function WorkflowIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v7a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 17a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1v-2zM14 17a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2z"
      />
    </svg>
  );
}

function BuilderIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
      />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 6.5a5.5 5.5 0 105.5 5.5A5.5 5.5 0 0012 6.5zm9 5.5a7.84 7.84 0 00-.14-1.45l2.05-1.6-2-3.46-2.47 1a8 8 0 00-2.51-1.46l-.38-2.62H9.45l-.38 2.62a8 8 0 00-2.51 1.46l-2.47-1-2 3.46 2.05 1.6A7.84 7.84 0 004 12c0 .49.05.97.14 1.45l-2.05 1.6 2 3.46 2.47-1a8 8 0 002.51 1.46l.38 2.62h4.1l.38-2.62a8 8 0 002.51-1.46l2.47 1 2-3.46-2.05-1.6c.09-.48.14-.96.14-1.45z"
      />
    </svg>
  );
}

function DatabaseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 7v10c0 2 2 3 8 3s8-1 8-3V7M4 7c0 2 2 3 8 3s8-1 8-3M4 7c0-2 2-3 8-3s8 1 8 3m0 5c0 2-2 3-8 3s-8-1-8-3"
      />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
}

function UserMenu({ collapsed = false }: { collapsed?: boolean }) {
  const { user, logout } = useAuth();
  const [showMenu, setShowMenu] = useState(false);

  if (!user) return null;

  const initials = user.username
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className={`flex items-center gap-3 w-full hover:bg-gray-800 rounded-lg transition ${
          collapsed ? "px-3 py-3 justify-center" : "px-4 py-3"
        }`}
      >
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          <span className="text-sm font-semibold">{initials}</span>
        </div>
        {!collapsed && (
          <>
            <div className="flex-1 min-w-0 text-left">
              <p className="text-sm font-medium truncate">{user.username}</p>
              <p className="text-xs text-gray-400 truncate">{user.email}</p>
            </div>
            <svg
              className={`w-4 h-4 text-gray-400 transition-transform ${
                showMenu ? "rotate-180" : ""
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </>
        )}
      </button>

      {showMenu && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowMenu(false)}
          />
          <div className="absolute bottom-full left-0 right-0 mb-2 bg-gray-800 rounded-lg shadow-lg overflow-hidden z-20">
            {user.is_admin && (
              <div className="px-4 py-2 bg-blue-900 text-blue-200 text-xs font-medium">
                Administrator
              </div>
            )}
            <button
              onClick={() => {
                setShowMenu(false);
                logout();
              }}
              className="w-full px-4 py-3 text-left text-sm text-gray-300 hover:bg-gray-700 transition flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function HamburgerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function CollapseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

