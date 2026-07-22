import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, CheckCircle2, Clock, Loader2, AlertCircle, ArrowRight } from "lucide-react";
import { fetchJob, getSSEEventSourceUrl } from "../api/client";
import { JobStatus, SSEEventData } from "../types";
import { useActiveJob } from "../state/JobContext";

export const VerificationStatusPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeJobId: jobId } = useActiveJob();
  const [status, setStatus] = useState<JobStatus>("queued");
  const [events, setEvents] = useState<SSEEventData[]>([]);

  useEffect(() => {
    if (!jobId) return;

    // Fetch initial status
    fetchJob(jobId)
      .then((j) => setStatus(j.status))
      .catch(() => {});

    // Setup real-time SSE stream
    const sse = new EventSource(getSSEEventSourceUrl(jobId), { withCredentials: true });

    sse.onmessage = (event) => {
      try {
        const data: SSEEventData = JSON.parse(event.data);
        setEvents((prev) => [data, ...prev]);

        if (data.status) {
          setStatus(data.status as JobStatus);
        }

        if (data.status === "completed" || data.event_type === "report.generated") {
          setTimeout(() => {
            navigate("/results");
          }, 1500);
        }
      } catch (err) {}
    };

    return () => {
      sse.close();
    };
  }, [jobId, navigate]);

  const stages: { key: JobStatus; label: string }[] = [
    { key: "queued", label: "Queued" },
    { key: "ocr_running", label: "OCR & Text Extraction" },
    { key: "face_verification", label: "Face Embedding Match" },
    { key: "matching", label: "Entity Matching & Scoring" },
    { key: "completed", label: "Verification Complete" },
  ];

  const getStageIndex = (st: JobStatus) => {
    switch (st) {
      case "queued":
        return 0;
      case "processing":
      case "ocr_running":
        return 1;
      case "face_verification":
        return 2;
      case "matching":
        return 3;
      case "completed":
        return 4;
      default:
        return 0;
    }
  };

  const currentIndex = getStageIndex(status);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="glass-panel p-6">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Activity className="w-5 h-5 text-indigo-400 animate-pulse" />
              <span>Real-Time Job Status Stream</span>
            </h2>
            <p className="text-xs text-slate-400 font-mono mt-1">Job ID: {jobId || "None Selected"}</p>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 uppercase">
            {status}
          </span>
        </div>

        {/* Stepper Progress Bar */}
        <div className="space-y-4 mb-8">
          <div className="grid grid-cols-5 gap-2">
            {stages.map((stage, idx) => {
              const isDone = idx < currentIndex || status === "completed";
              const isCurrent = idx === currentIndex && status !== "completed";
              return (
                <div key={stage.key} className="text-center">
                  <div
                    className={`h-2 rounded-full mb-2 transition-all ${
                      isDone
                        ? "bg-emerald-500 shadow-md shadow-emerald-500/20"
                        : isCurrent
                        ? "bg-indigo-500 animate-pulse"
                        : "bg-slate-800"
                    }`}
                  />
                  <span
                    className={`text-[10px] block font-medium ${
                      isDone ? "text-emerald-400" : isCurrent ? "text-indigo-400" : "text-slate-500"
                    }`}
                  >
                    {stage.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {status === "completed" && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center mb-6">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-emerald-400">Verification Completed Successfully</h3>
            <p className="text-xs text-slate-300 mt-1">Redirecting to detailed report...</p>
            <button
              onClick={() => navigate("/results")}
              className="mt-3 glass-button inline-flex items-center space-x-2 text-xs"
            >
              <span>View Report Now</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Real-time Event Log */}
        <div>
          <h3 className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-wider">Live Event Stream</h3>
          <div className="bg-slate-950/80 rounded-xl border border-slate-800 p-4 font-mono text-xs max-h-60 overflow-y-auto space-y-2">
            {events.length === 0 ? (
              <div className="text-slate-500 flex items-center space-x-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Listening for server-sent events...</span>
              </div>
            ) : (
              events.map((evt, i) => (
                <div key={i} className="flex items-start space-x-2 text-slate-300 border-b border-slate-900 pb-1">
                  <span className="text-indigo-400">[{evt.event_type}]</span>
                  <span>{JSON.stringify(evt)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
