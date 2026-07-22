import React, { createContext, useContext, useMemo, useState } from "react";

interface JobContextValue {
  activeJobId: string | null;
  setActiveJobId: (jobId: string | null) => void;
  clearActiveJob: () => void;
}

const JobContext = createContext<JobContextValue | undefined>(undefined);

export const JobProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const value = useMemo(
    () => ({
      activeJobId,
      setActiveJobId,
      clearActiveJob: () => setActiveJobId(null),
    }),
    [activeJobId]
  );

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>;
};

export function useActiveJob(): JobContextValue {
  const context = useContext(JobContext);
  if (!context) {
    throw new Error("useActiveJob must be used within JobProvider");
  }
  return context;
}
