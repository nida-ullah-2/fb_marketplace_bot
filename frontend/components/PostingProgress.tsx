"use client";

import React, { useEffect, useState } from "react";
import { PostingJob } from "@/types";

interface PostingProgressProps {
  jobId: string;
  onComplete?: () => void;
}

export default function PostingProgress({
  jobId,
  onComplete,
}: PostingProgressProps) {
  const [job, setJob] = useState<PostingJob | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let pollInterval: NodeJS.Timeout | null = null;
    let usePolling = false;

    // Try SSE first, fallback to polling if it fails
    try {
      // Server-Sent Events (SSE) connection for real-time updates
      eventSource = new EventSource(
        `http://localhost:8000/api/posts/status-stream/${jobId}/`
      );

      eventSource.onopen = () => {
        console.log("✅ SSE connection established");
        setIsConnected(true);
        setError(null);
        usePolling = false;
      };

      eventSource.onmessage = (event) => {
        try {
          const data: PostingJob = JSON.parse(event.data);
          console.log("📊 Progress update:", data);
          setJob(data);

          // Close connection when job is complete or failed
          if (data.status === "completed" || data.status === "failed") {
            console.log("🏁 Job finished, closing SSE connection");
            eventSource?.close();
            setIsConnected(false);

            // Call onComplete callback after 2 seconds
            setTimeout(() => {
              onComplete?.();
            }, 2000);
          }
        } catch (err) {
          console.error("❌ Failed to parse SSE data:", err);
        }
      };

      eventSource.onerror = (err) => {
        console.warn("⚠️ SSE not available, falling back to polling");
        setIsConnected(false);
        eventSource?.close();
        usePolling = true;

        // Start polling as fallback
        startPolling();
      };
    } catch (err) {
      console.warn("⚠️ SSE not supported, using polling");
      startPolling();
    }

    // Fallback polling mechanism
    function startPolling() {
      const poll = async () => {
        try {
          const token = localStorage.getItem("token");
          const response = await fetch(
            `http://localhost:8000/api/posts/job-status/${jobId}/`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          );

          if (response.ok) {
            const data: PostingJob = await response.json();
            console.log("📊 Polling update:", data);
            setJob(data);
            setIsConnected(true);

            // Stop polling when job is complete
            if (data.status === "completed" || data.status === "failed") {
              console.log("🏁 Job finished, stopping polling");
              if (pollInterval) clearInterval(pollInterval);

              setTimeout(() => {
                onComplete?.();
              }, 2000);
            }
          }
        } catch (err) {
          console.error("❌ Polling error:", err);
        }
      };

      // Initial poll
      poll();

      // Poll every 2 seconds
      pollInterval = setInterval(poll, 2000);
    }

    // Cleanup on unmount
    return () => {
      console.log("🧹 Cleaning up connection");
      if (eventSource) {
        eventSource.close();
      }
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [jobId, onComplete]);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800 text-sm">❌ {error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full"></div>
          <p className="text-blue-800 text-sm">Connecting to job...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      {/* Connection status */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Posting Progress
        </h3>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              isConnected ? "bg-green-500 animate-pulse" : "bg-gray-300"
            }`}
          ></span>
          <span className="text-xs text-gray-600">
            {isConnected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Job status */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600">Status:</span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              job.status === "completed"
                ? "bg-green-100 text-green-800"
                : job.status === "failed"
                ? "bg-red-100 text-red-800"
                : job.status === "running"
                ? "bg-blue-100 text-blue-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {job.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600">Progress:</span>
          <span className="text-sm font-medium text-gray-900">
            {job.progress_percentage}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ease-out ${
              job.status === "completed"
                ? "bg-green-600"
                : job.status === "failed"
                ? "bg-red-600"
                : "bg-blue-600"
            }`}
            style={{ width: `${job.progress_percentage}%` }}
          ></div>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <p className="text-2xl font-bold text-gray-900">{job.total_posts}</p>
          <p className="text-xs text-gray-600">Total</p>
        </div>
        <div className="text-center p-3 bg-green-50 rounded-lg">
          <p className="text-2xl font-bold text-green-600">
            {job.completed_posts}
          </p>
          <p className="text-xs text-gray-600">Completed</p>
        </div>
        <div className="text-center p-3 bg-red-50 rounded-lg">
          <p className="text-2xl font-bold text-red-600">{job.failed_posts}</p>
          <p className="text-xs text-gray-600">Failed</p>
        </div>
      </div>

      {/* Current post being processed */}
      {job.current_post_title && job.status === "running" && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-xs text-blue-600 mb-1">Currently posting:</p>
          <p className="text-sm font-medium text-blue-900 truncate">
            {job.current_post_title}
          </p>
        </div>
      )}

      {/* Error message */}
      {job.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mt-4">
          <p className="text-xs text-red-600 mb-1">Error:</p>
          <p className="text-sm text-red-900">{job.error_message}</p>
        </div>
      )}

      {/* Completion message */}
      {job.status === "completed" && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mt-4">
          <p className="text-sm font-medium text-green-900 text-center">
            🎉 All posts completed successfully!
          </p>
        </div>
      )}
    </div>
  );
}
