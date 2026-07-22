import React from "react";
import { Settings, ShieldCheck, Server, Lock, Ban } from "lucide-react";
import { API_BASE } from "../api/client";

export const SettingsPage: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="glass-panel p-6">
        <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-slate-800">
          <Settings className="w-6 h-6 text-indigo-400" />
          <div>
            <h2 className="text-lg font-bold text-white">Production Security Settings</h2>
            <p className="text-xs text-slate-400">Public frontend runtime configuration</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/50">
            <div className="flex items-center space-x-2 mb-2">
              <Server className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-bold text-white">API Gateway</span>
            </div>
            <span className="text-xs text-slate-400 font-mono break-all">{API_BASE}</span>
          </div>

          <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/50">
            <div className="flex items-center space-x-2 mb-2">
              <Lock className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-bold text-white">Credential Exposure</span>
            </div>
            <span className="text-xs text-slate-400">No storage keys, API tokens, or database credentials are bundled.</span>
          </div>

          <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/50">
            <div className="flex items-center space-x-2 mb-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-bold text-white">Browser Persistence</span>
            </div>
            <span className="text-xs text-slate-400">Job state is kept in memory and cleared on browser refresh.</span>
          </div>

          <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/50">
            <div className="flex items-center space-x-2 mb-2">
              <Ban className="w-4 h-4 text-rose-400" />
              <span className="text-sm font-bold text-white">Storage Configuration</span>
            </div>
            <span className="text-xs text-slate-400">Object storage is configured only in the backend hosting layer.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
