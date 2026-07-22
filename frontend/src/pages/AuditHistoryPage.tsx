import React, { useEffect, useState } from "react";
import { History, Shield, RefreshCw, FileText } from "lucide-react";
import { fetchAuditLogs } from "../api/client";
import { AuditLogItem } from "../types";

export const AuditHistoryPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogs(50);
      setLogs(data);
    } catch (err) {
      setLogs([]);
      setError("Audit access is restricted.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center space-x-2">
            <History className="w-6 h-6 text-indigo-400" />
            <span>Security & Compliance Audit Trail</span>
          </h1>
          <p className="text-xs text-slate-400">Immutable audit records for compliance and regulatory reporting</p>
        </div>
        <button onClick={loadLogs} className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 inline-flex items-center space-x-1.5">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Logs</span>
        </button>
      </div>

      <div className="glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Resource Type</th>
                <th className="px-4 py-3">Resource ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">Loading audit records...</td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">{error}</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">No audit records found</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-900/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-slate-400">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 font-semibold text-indigo-400">{log.action}</td>
                    <td className="px-4 py-3 text-slate-300">{log.resource_type}</td>
                    <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">{log.resource_id || "N/A"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
