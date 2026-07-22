import React from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { DashboardPage } from "./pages/DashboardPage";
import { UploadKycPage } from "./pages/UploadKycPage";
import { UploadSupportingPage } from "./pages/UploadSupportingPage";
import { VerificationStatusPage } from "./pages/VerificationStatusPage";
import { VerificationResultsPage } from "./pages/VerificationResultsPage";
import { AuditHistoryPage } from "./pages/AuditHistoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import { JobProvider } from "./state/JobContext";

export const App: React.FC = () => {
  return (
    <HashRouter>
      <JobProvider>
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/upload-primary" element={<UploadKycPage />} />
              <Route path="/upload-supporting" element={<UploadSupportingPage />} />
              <Route path="/status" element={<VerificationStatusPage />} />
              <Route path="/results" element={<VerificationResultsPage />} />
              <Route path="/audit" element={<AuditHistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </main>
          <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
            Startrit Identity Verification Platform &copy; 2026. Enterprise Production Quality.
          </footer>
        </div>
      </JobProvider>
    </HashRouter>
  );
};
export default App;
