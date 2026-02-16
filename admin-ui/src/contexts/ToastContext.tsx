"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "success", duration: number = 3000) => {
    const id = Math.random().toString(36).substring(7);
    const newToast: Toast = { id, message, type };
    
    setToasts((prev) => [...prev, newToast]);

    // Auto-dismiss after duration
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return (
    <>
      <style>{`
        @keyframes slide-in-right {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
      
      <ToastContext.Provider value={{ showToast }}>
        {children}
        
        {/* Toast Container */}
        <div 
          className="fixed top-4 right-4 space-y-2 pointer-events-none"
          style={{ zIndex: 9999 }}
        >
          {toasts.map((toast) => (
            <div key={toast.id} className="pointer-events-auto">
              <ToastNotification
                message={toast.message}
                type={toast.type}
                onClose={() => removeToast(toast.id)}
              />
            </div>
          ))}
        </div>
      </ToastContext.Provider>
    </>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}

interface ToastNotificationProps {
  message: string;
  type: ToastType;
  onClose: () => void;
}

function ToastNotification({ message, type, onClose }: ToastNotificationProps) {
  const styleConfig = {
    success: {
      borderColor: '#86efac',
      iconColor: '#22c55e',
      title: "Success",
      iconPath: (
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      ),
    },
    error: {
      borderColor: '#fecaca',
      iconColor: '#ef4444',
      title: "Error",
      iconPath: (
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
      ),
    },
    info: {
      borderColor: '#bfdbfe',
      iconColor: '#3b82f6',
      title: "Info",
      iconPath: (
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
      ),
    },
    warning: {
      borderColor: '#fde68a',
      iconColor: '#eab308',
      title: "Warning",
      iconPath: (
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      ),
    },
  };

  const config = styleConfig[type];

  return (
    <div 
      className="animate-slide-in-right"
      style={{
        animation: 'slide-in-right 0.3s ease-out',
      }}
    >
      <div 
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '0.5rem',
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          border: `2px solid ${config.borderColor}`,
          padding: '1rem',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          minWidth: '320px',
          maxWidth: '28rem',
        }}
      >
        <div style={{ flexShrink: 0 }}>
          <svg 
            style={{ width: '1.25rem', height: '1.25rem', color: config.iconColor }} 
            fill="currentColor" 
            viewBox="0 0 20 20"
          >
            {config.iconPath}
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: '0.875rem', fontWeight: 600, color: '#111827', margin: 0 }}>
            {config.title}
          </p>
          <p style={{ fontSize: '0.875rem', color: '#4b5563', marginTop: '0.125rem', marginBottom: 0 }}>
            {message}
          </p>
        </div>
        <button
          onClick={onClose}
          style={{
            flexShrink: 0,
            color: '#9ca3af',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#4b5563'}
          onMouseLeave={(e) => e.currentTarget.style.color = '#9ca3af'}
        >
          <svg style={{ width: '1rem', height: '1rem' }} fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
}
