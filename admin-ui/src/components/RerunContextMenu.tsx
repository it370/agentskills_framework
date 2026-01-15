"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { rerunWorkflow, getRunMetadata } from "../lib/api";

interface RerunContextMenuProps {
  threadId: string;
  className?: string;
  onError?: (error: string) => void;
}

export default function RerunContextMenu({
  threadId,
  className = "",
  onError,
}: RerunContextMenuProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);

  const handleRerunAsIs = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen(false);
    
    if (!confirm('Rerun workflow with same inputs?')) {
      return;
    }
    
    setIsRerunning(true);
    try {
      // Generate ACK key for instant redirect
      const ackKey = `ack_${crypto.randomUUID()}`;
      console.log("[Rerun] Starting rerun with ack_key:", ackKey);
      
      // Subscribe to ACK event via global event bus
      const { adminEvents } = await import("../lib/adminEvents");
      
      let ackReceived = false;
      const unsubscribe = adminEvents.once('ack', (event: any) => {
        if (event.ack_key === ackKey) {
          console.log("[Rerun] ✅ ACK received! Redirecting immediately...");
          ackReceived = true;
          // Redirect IMMEDIATELY on ACK
          router.push(`/admin/${event.thread_id}`);
        }
      });
      
      // Call rerun API with ACK key (backend will send ACK via Pusher)
      const result = await rerunWorkflow(threadId, ackKey);
      console.log("[Rerun] HTTP response:", result);
      
      // If ACK hasn't arrived yet, wait a bit then redirect (fallback)
      if (!ackReceived) {
        console.log("[Rerun] ACK not received, redirecting via HTTP response");
        setTimeout(() => {
          unsubscribe();
          router.push(`/admin/${result.thread_id}`);
        }, 100);
      }
    } catch (err: any) {
      console.error("[Rerun] Error:", err);
      if (onError) {
        onError(err.message || "Failed to rerun workflow");
      } else {
        alert(`Failed to rerun: ${err.message}`);
      }
    } finally {
      setIsRerunning(false);
    }
  };

  const handleEditAndRerun = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen(false);
    
    try {
      // Fetch the run metadata
      const metadata = await getRunMetadata(threadId);
      
      // Store data in sessionStorage to avoid URL length issues
      sessionStorage.setItem('rerun_config', JSON.stringify({
        runName: metadata.run_name || '',
        sop: metadata.sop,
        initialData: metadata.initial_data
      }));
      
      // Navigate to new run page with just a flag
      router.push('/runs/new?from=rerun');
    } catch (err: any) {
      console.error("[EditRerun] Error:", err);
      if (onError) {
        onError(`Failed to load run data: ${err.message}`);
      } else {
        alert(`Failed to load run data: ${err.message}`);
      }
    }
  };

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="p-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
        title="Rerun options"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
          />
        </svg>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <>
          {/* Backdrop to close menu */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Menu */}
          <div className="absolute right-0 mt-2 w-56 rounded-lg shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-20">
            <div className="py-1">
              <button
                onClick={handleRerunAsIs}
                disabled={isRerunning}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                {isRerunning ? 'Rerunning...' : 'Rerun as is'}
              </button>
              
              <button
                onClick={handleEditAndRerun}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
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
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                  />
                </svg>
                Edit and rerun
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
