import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ArrowRight, Camera, CheckCircle2, Clock, AlertTriangle, FileText, UserCheck } from "lucide-react";

export const DashboardPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="glass-panel p-8 relative overflow-hidden bg-gradient-to-r from-indigo-950/40 via-slate-900/60 to-violet-950/40 border-indigo-900/30">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold mb-4">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>AI Face Verification Engine Active</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl mb-3">
            Real-Time AI Face Verification
          </h1>
          <p className="text-slate-400 text-sm leading-relaxed mb-6">
            Compare face embeddings between primary ID document photos and live selfies with feature distance and similarity scoring.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link to="/upload-primary" className="glass-button flex items-center space-x-2">
              <Camera className="w-4 h-4" />
              <span>Start Face Verification</span>
            </Link>
            <Link
              to="/audit"
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition-all flex items-center space-x-2"
            >
              <FileText className="w-4 h-4" />
              <span>View Audit Trail</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Quick Access Step Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-panel p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <Camera className="w-5 h-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Step 1: Upload Primary ID Photo</h3>
          <p className="text-xs text-slate-400">
            Upload government issued ID card containing face photo (PAN, Passport, Aadhaar, Driving License).
          </p>
          <Link to="/upload-primary" className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center space-x-1">
            <span>Proceed to Step 1</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="glass-panel p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
            <UserCheck className="w-5 h-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Step 2: Upload Live Selfie Photo</h3>
          <p className="text-xs text-slate-400">
            Upload live selfie or secondary face photo image to run real-time face embedding comparison.
          </p>
          <Link to="/upload-supporting" className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center space-x-1">
            <span>Proceed to Step 2</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
};
