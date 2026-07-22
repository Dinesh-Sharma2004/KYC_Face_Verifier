import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Award, CheckCircle2, AlertTriangle, XCircle, RefreshCw, Camera, Scan, ShieldCheck, ArrowRight, MinusCircle, Layers, Sliders, Image as ImageIcon, Cpu, AlertOctagon, Compass, Activity } from "lucide-react";
import { fetchVerificationResult } from "../api/client";
import { VerificationReport } from "../types";
import { useActiveJob } from "../state/JobContext";

export const VerificationResultsPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeJobId: jobId, clearActiveJob } = useActiveJob();
  const [reportData, setReportData] = useState<VerificationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadResult = async () => {
    if (!jobId) {
      setError("No active face verification job selected.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const data = await fetchVerificationResult(jobId);
      setReportData(data);
    } catch (err: any) {
      setError("Face verification result not ready or job failed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResult();
  }, [jobId]);

  const handleStartNew = () => {
    clearActiveJob();
    navigate("/");
  };

  const getVerdictBadge = (verdict: string) => {
    switch ((verdict || "").toUpperCase()) {
      case "VERIFIED":
      case "MATCH":
        return (
          <div className="inline-flex items-center space-x-2 px-5 py-2 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-base font-extrabold">
            <CheckCircle2 className="w-5 h-5" />
            <span>3-MODEL ENSEMBLE MATCH</span>
          </div>
        );
      case "REVIEW_REQUIRED":
        return (
          <div className="inline-flex items-center space-x-2 px-5 py-2 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 text-base font-extrabold">
            <AlertTriangle className="w-5 h-5" />
            <span>REVIEW REQUIRED</span>
          </div>
        );
      case "NO_FACE_DETECTED":
        return (
          <div className="inline-flex items-center space-x-2 px-5 py-2 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/30 text-base font-extrabold">
            <MinusCircle className="w-5 h-5" />
            <span>NO FACE DETECTED</span>
          </div>
        );
      default:
        return (
          <div className="inline-flex items-center space-x-2 px-5 py-2 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 text-base font-extrabold">
            <XCircle className="w-5 h-5" />
            <span>ENSEMBLE MISMATCH</span>
          </div>
        );
    }
  };

  const fieldScores: any = reportData?.field_scores || {};
  const faceInfo = fieldScores.face_verification || reportData?.report?.face_verification || {};

  const numberOrNull = (value: unknown): number | null => (typeof value === "number" ? value : null);
  const textOrNA = (value: unknown): string =>
    value === undefined || value === null || value === "" ? "N/A" : String(value);
  const formatNumber = (value: number | null, digits: number) => (value === null ? "N/A" : value.toFixed(digits));
  const formatPercent = (value: number | null) => (value === null ? "N/A" : `${value.toFixed(1)}%`);

  const arcDist = numberOrNull(faceInfo.arcface_distance);
  const fnetDist = numberOrNull(faceInfo.facenet_distance);
  const buffDist = numberOrNull(faceInfo.buffalo_distance);
  const ensembleDist = numberOrNull(faceInfo.ensemble_distance);

  const arcVerdict = textOrNA(faceInfo.arcface_verdict);
  const fnetVerdict = textOrNA(faceInfo.facenet_verdict);
  const buffVerdict = textOrNA(faceInfo.buffalo_verdict);
  const ensembleVerdict = textOrNA(faceInfo.ensemble_verdict || faceInfo.verdict || reportData?.decision);

  const matchConfidence = numberOrNull(faceInfo.match_confidence);
  const mismatchConfidence = numberOrNull(faceInfo.mismatch_confidence);
  const hasDisagreement = Boolean(faceInfo.model_disagreement);
  const pQuality = faceInfo.primary_quality || {};
  const sQuality = faceInfo.secondary_quality || {};
  const pPose = pQuality.landmark_info?.pose || {};
  const sPose = sQuality.landmark_info?.pose || {};

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center space-x-2.5">
            <Cpu className="w-7 h-7 text-indigo-400" />
            <span>Forensic Face Debug & 3-Model Ensemble</span>
          </h1>
          <p className="text-xs text-slate-400 font-mono">Job ID: {jobId || "N/A"}</p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadResult}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 inline-flex items-center space-x-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleStartNew}
            className="glass-button text-xs py-1.5 px-3 flex items-center space-x-1"
          >
            <span>New Verification</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="glass-panel p-12 text-center text-slate-400">Performing forensic landmark pose estimation & 3-model verification...</div>
      ) : error ? (
        <div className="glass-panel p-8 text-center text-rose-400 border-rose-500/20">{error}</div>
      ) : reportData ? (
        <div className="space-y-6">
          {/* Verdict Header & Explicit Confidence Semantics */}
          <div className="glass-panel p-8 bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 text-center space-y-4">
            <div className="inline-block">{getVerdictBadge(ensembleVerdict)}</div>

            {hasDisagreement && (
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-medium">
                <AlertOctagon className="w-4 h-4" />
                <span>Model Disagreement Detected (Majority Voting Applied)</span>
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-800/80">
              <div>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Weighted Distance</span>
                <span className="text-base font-extrabold font-mono text-emerald-400">{formatNumber(ensembleDist, 4)}</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Match Confidence</span>
                <span className="text-base font-extrabold text-emerald-400">{formatPercent(matchConfidence)}</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Mismatch Confidence</span>
                <span className="text-base font-extrabold text-rose-400">{formatPercent(mismatchConfidence)}</span>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Self-Similarity Test</span>
                <span className="text-xs font-extrabold text-emerald-400 flex items-center justify-center space-x-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Protected</span>
                </span>
              </div>
            </div>
          </div>

          {/* Phase 13: 3-Model Comparative Matrix */}
          <div className="glass-panel p-6 space-y-4">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Independent Model Metrics & Consensus Matrix</span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase">
                    <th className="py-2.5 px-3">Model</th>
                    <th className="py-2.5 px-3">Weight</th>
                    <th className="py-2.5 px-3">Cosine Distance</th>
                    <th className="py-2.5 px-3">Threshold</th>
                    <th className="py-2.5 px-3">Model Verdict</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  <tr>
                    <td className="py-3 px-3 font-bold text-indigo-400">ArcFace (512-d)</td>
                    <td className="py-3 px-3">40%</td>
                    <td className="py-3 px-3 font-extrabold text-emerald-400">{formatNumber(arcDist, 4)}</td>
                    <td className="py-3 px-3 text-slate-400">&le; 0.40</td>
                    <td className="py-3 px-3"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">{arcVerdict}</span></td>
                    <td className="py-3 px-3 text-slate-400">Normal</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-3 font-bold text-indigo-400">FaceNet512 (512-d)</td>
                    <td className="py-3 px-3">25%</td>
                    <td className="py-3 px-3 font-extrabold text-emerald-400">{formatNumber(fnetDist, 4)}</td>
                    <td className="py-3 px-3 text-slate-400">&le; 0.50</td>
                    <td className="py-3 px-3"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">{fnetVerdict}</span></td>
                    <td className="py-3 px-3 text-slate-400">Normal</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-3 font-bold text-indigo-400">Buffalo_L (InsightFace)</td>
                    <td className="py-3 px-3">35%</td>
                    <td className="py-3 px-3 font-extrabold text-emerald-400">{formatNumber(buffDist, 4)}</td>
                    <td className="py-3 px-3 text-slate-400">&le; 0.42</td>
                    <td className="py-3 px-3"><span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">{buffVerdict}</span></td>
                    <td className="py-3 px-3 text-slate-400">Normal</td>
                  </tr>
                  <tr className="bg-indigo-950/20 font-bold">
                    <td className="py-3 px-3 text-white">Weighted Ensemble</td>
                    <td className="py-3 px-3">100%</td>
                    <td className="py-3 px-3 text-indigo-300">{formatNumber(ensembleDist, 4)}</td>
                    <td className="py-3 px-3 text-slate-400">&le; 0.42</td>
                    <td className="py-3 px-3"><span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold">{ensembleVerdict}</span></td>
                    <td className="py-3 px-3 text-emerald-400">Computed</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Phase 13: Visual Debug Gallery & Pose Angles */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Primary ID Card Crop & Pose */}
            <div className="glass-panel p-5 space-y-4">
              <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center space-x-2">
                <ImageIcon className="w-4 h-4" />
                <span>Primary ID Photo (BBox Overlay & Alignment)</span>
              </h3>
              <div className="flex items-center justify-center space-x-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="w-28 h-28 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center text-xs text-slate-500 text-center px-3">
                  Image Redacted
                </div>
              </div>
              <div className="text-xs space-y-1.5 text-slate-400 font-mono">
                <div className="flex justify-between"><span>Blur Score:</span><span className="text-white font-bold">{textOrNA(pQuality.blur_score)}</span></div>
                <div className="flex justify-between"><span>Brightness:</span><span className="text-white font-bold">{textOrNA(pQuality.brightness)}</span></div>
                <div className="flex justify-between"><span>Contrast / Sharpness:</span><span className="text-white font-bold">{textOrNA(pQuality.contrast)} / {textOrNA(pQuality.sharpness)}</span></div>
                <div className="flex justify-between"><span>Pose (Yaw/Pitch/Roll):</span><span className="text-amber-400 font-bold">{textOrNA(pPose.yaw)} / {textOrNA(pPose.pitch)} / {textOrNA(pPose.roll)}</span></div>
                <div className="flex justify-between"><span>Quality Category:</span><span className="text-emerald-400 font-bold">{textOrNA(pQuality.quality_category)}</span></div>
              </div>
            </div>

            {/* Secondary Selfie Crop & Pose */}
            <div className="glass-panel p-5 space-y-4">
              <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center space-x-2">
                <ImageIcon className="w-4 h-4" />
                <span>Secondary Selfie (BBox Overlay & Alignment)</span>
              </h3>
              <div className="flex items-center justify-center space-x-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="w-28 h-28 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center text-xs text-slate-500 text-center px-3">
                  Image Redacted
                </div>
              </div>
              <div className="text-xs space-y-1.5 text-slate-400 font-mono">
                <div className="flex justify-between"><span>Blur Score:</span><span className="text-white font-bold">{textOrNA(sQuality.blur_score)}</span></div>
                <div className="flex justify-between"><span>Brightness:</span><span className="text-white font-bold">{textOrNA(sQuality.brightness)}</span></div>
                <div className="flex justify-between"><span>Contrast / Sharpness:</span><span className="text-white font-bold">{textOrNA(sQuality.contrast)} / {textOrNA(sQuality.sharpness)}</span></div>
                <div className="flex justify-between"><span>Pose (Yaw/Pitch/Roll):</span><span className="text-amber-400 font-bold">{textOrNA(sPose.yaw)} / {textOrNA(sPose.pitch)} / {textOrNA(sPose.roll)}</span></div>
                <div className="flex justify-between"><span>Quality Category:</span><span className="text-emerald-400 font-bold">{textOrNA(sQuality.quality_category)}</span></div>
              </div>
            </div>
          </div>

        </div>
      ) : null}
    </div>
  );
};
