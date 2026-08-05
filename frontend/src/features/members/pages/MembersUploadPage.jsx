import { motion } from "framer-motion";
import { FileSpreadsheet, LoaderCircle, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Stepper } from "../../../components/ui/Stepper";
import { UploadZone } from "../../../components/ui/UploadZone";

export function MembersUploadPage() {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a CSV file.");
      return;
    }
    setError("");
    setSelectedFile(file);
  };

  const handleContinue = () => {
    if (!selectedFile) return;
    setIsLoading(true);
    navigate("/single-upload/members/processing", {
      state: { file: selectedFile },
    });
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
            Members workflow
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-slate-50">
            Upload an members dataset
          </h1>
          <p className="mt-2 max-w-2xl text-slate-600 dark:text-slate-400">
            Prepare your CSV for a structured validation pass with field-level
            checks and business rules.
          </p>
        </div>
        <Stepper currentStep={2} />
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
        <Card className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950 dark:text-slate-50">
                Upload members CSV
              </h2>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                Use the file picker below to choose a CSV file for validation.
              </p>
            </div>
            <Badge tone="info">CSV only</Badge>
          </div>

          <UploadZone
            onFileSelect={handleFileSelect}
            fileName={selectedFile?.name}
          />

          {error ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-300">
              {error}
            </div>
          ) : null}

          {selectedFile ? (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-3xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-900/60"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-white p-2.5 shadow-sm dark:bg-slate-950">
                    <FileSpreadsheet
                      size={18}
                      className="text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <p className="font-medium text-slate-900 dark:text-slate-100">
                      {selectedFile.name}
                    </p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {Math.round(selectedFile.size / 1024)} KB
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </motion.div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Button
              onClick={handleContinue}
              disabled={!selectedFile || isLoading}
              className="gap-2"
            >
              {isLoading ? (
                <LoaderCircle size={16} className="animate-spin" />
              ) : null}
              Validate File
            </Button>
            <Button variant="secondary">Use sample file</Button>
          </div>
        </Card>

        <Card className="space-y-5">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
              What happens next
            </p>
            <h3 className="mt-2 text-xl font-semibold text-slate-950 dark:text-slate-50">
              A guided validation run
            </h3>
          </div>
          <div className="space-y-3 text-sm text-slate-600 dark:text-slate-400">
            <div className="rounded-2xl border border-slate-200 bg-white/70 p-4 dark:border-slate-800 dark:bg-slate-900/60">
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                Structured checks
              </p>
              <p className="mt-1">
                A validation engine inspects required fields, formatting,
                duplicates, and business rules.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 p-4 dark:border-slate-800 dark:bg-slate-900/60">
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                Smart review
              </p>
              <p className="mt-1">
                The review page highlights warnings and errors so you can act
                confidently.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 p-4 dark:border-slate-800 dark:bg-slate-900/60">
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                Export-ready outputs
              </p>
              <p className="mt-1">
                Corrected CSVs, error reports, and summaries are generated for
                downstream action.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
