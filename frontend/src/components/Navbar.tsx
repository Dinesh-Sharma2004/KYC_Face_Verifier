import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Camera,
  UserCheck,
  Activity,
  Award,
  History,
  Settings,
  ShieldCheck,
} from "lucide-react";

export const Navbar: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { label: "Dashboard", path: "/", icon: LayoutDashboard },
    { label: "1. Upload ID Photo", path: "/upload-primary", icon: Camera },
    { label: "2. Upload Selfie", path: "/upload-supporting", icon: UserCheck },
    { label: "Live Status", path: "/status", icon: Activity },
    { label: "Face Match Results", path: "/results", icon: Award },
    { label: "Audit Trail", path: "/audit", icon: History },
    { label: "Settings", path: "/settings", icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <Link to="/" className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <ShieldCheck className="w-6 h-6 text-white" />
              </div>
              <div>
                <span className="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
                  Startrit Face Verification
                </span>
                <span className="block text-xs text-indigo-400 font-mono">v3.0 Production</span>
              </div>
            </Link>
          </div>

          <nav className="hidden md:flex space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
};
