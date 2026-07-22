import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, CheckCircle2, ArrowRight, Loader2, Camera, RefreshCw } from "lucide-react";
import { uploadDocument, triggerProcessing, fetchJob } from "../api/client";
import { DocumentMeta } from "../types";
import { useActiveJob } from "../state/JobContext";

export const UploadSupportingPage: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadedDoc, setUploadedDoc] = useState<DocumentMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkingExisting, setCheckingExisting] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { activeJobId, clearActiveJob } = useActiveJob();

  useEffect(() => {
    if (!activeJobId) {
      setCheckingExisting(false);
      return;
    }

    fetchJob(activeJobId)
      .then((job) => {
        const supporting = job.documents?.find((d) => d.role === "supporting");
        if (supporting) {
          setUploadedDoc(supporting);
        }
      })
      .catch(() => {
        clearActiveJob();
      })
      .finally(() => {
        setCheckingExisting(false);
      });
  }, [activeJobId, clearActiveJob]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setError(null);

      if (selected.type.startsWith("image/")) {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(URL.createObjectURL(selected));
      } else {
        setPreviewUrl(null);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!activeJobId) {
      setError("No active job session found. Please upload primary ID photo first.");
      return;
    }

    if (!file && !uploadedDoc) {
      setError("Please select a selfie or secondary face photo image.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (file) {
        const res = await uploadDocument(activeJobId, file, "supporting", "SELFIE");
        setUploadedDoc({
          document_id: res.document_id,
          role: "supporting",
          filename: res.filename,
          content_type: res.content_type,
          size_bytes: res.size_bytes,
        });
      }

      await triggerProcessing(activeJobId);
      navigate("/status");
    } catch (err: any) {
      setError(err.message || "Failed to upload secondary selfie image");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="glass-panel p-6">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center font-bold text-sm">
              2
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <Camera className="w-5 h-5 text-indigo-400" />
                <span>Upload Selfie / Secondary Face Photo</span>
              </h2>
              <p className="text-xs text-slate-400">Select live selfie or secondary photo for face matching</p>
            </div>
          </div>
          {uploadedDoc && (
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Saved</span>
            </span>
          )}
        </div>

        {checkingExisting ? (
          <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            <span>Checking job status...</span>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            {uploadedDoc && !file && (
              <div className="p-4 rounded-xl bg-slate-900/80 border border-emerald-500/30 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                    <Camera className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">{uploadedDoc.filename}</h4>
                    <span className="text-[11px] text-slate-400 font-mono block">
                      {(uploadedDoc.size_bytes / 1024).toFixed(1)} KB • Selfie Image
                    </span>
                  </div>
                </div>
                <label
                  htmlFor="file-upload-replace-sup"
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 cursor-pointer inline-flex items-center space-x-1"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Replace</span>
                </label>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                {uploadedDoc && !file ? "Replace Selfie Photo (Optional)" : "Selfie / Secondary Face Image"}
              </label>
              <div className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-xl p-6 text-center transition-all bg-slate-900/30">
                <input
                  type="file"
                  id={uploadedDoc && !file ? "file-upload-replace-sup" : "file-upload-sup"}
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label
                  htmlFor={uploadedDoc && !file ? "file-upload-replace-sup" : "file-upload-sup"}
                  className="cursor-pointer space-y-3 block"
                >
                  {previewUrl ? (
                    <div className="space-y-2">
                      <img src={previewUrl} alt="Secondary Face Preview" className="max-h-48 mx-auto rounded-lg border border-slate-700 shadow-md" />
                      <div className="text-xs font-medium text-emerald-400 flex items-center justify-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{file?.name} ({(file?.size! / 1024).toFixed(1)} KB)</span>
                      </div>
                    </div>
                  ) : file ? (
                    <div className="text-sm font-medium text-emerald-400 flex items-center justify-center space-x-2">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  ) : (
                    <div>
                      <div className="w-12 h-12 rounded-full bg-slate-800 text-indigo-400 mx-auto flex items-center justify-center mb-2">
                        <Upload className="w-6 h-6" />
                      </div>
                      <span className="text-sm font-medium text-indigo-400">Click to upload Selfie image</span>
                      <span className="text-xs text-slate-500 block mt-1">PNG, JPG, or JPEG selfie photo</span>
                    </div>
                  )}
                </label>
              </div>
            </div>

            {error && <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">{error}</div>}

            <button
              type="submit"
              disabled={loading || (!file && !uploadedDoc)}
              className="w-full glass-button flex items-center justify-center space-x-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Starting Face Verification...</span>
                </>
              ) : (
                <>
                  <span>Run Face Verification</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
