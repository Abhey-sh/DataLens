import { motion } from "framer-motion";
import { ArrowRight, CircleAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { importTypes } from "../constants/importTypes";

export function ImportTypePage() {
  const [selectedType, setSelectedType] = useState(importTypes[0]);
  const navigate = useNavigate();

  const handleContinue = () => {
    if (selectedType?.status === "active") {
      navigate(selectedType.uploadRoute);
    }
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
      <div className="space-y-6">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
            Workflow
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-slate-50">
            Validate Import Data
          </h1>
          <p className="max-w-2xl text-slate-600 dark:text-slate-400">
            Choose the import family you want to validate. Only Members is
            available in this release.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {importTypes.map((type) => {
            const Icon = type.icon;
            const isSelected = selectedType?.id === type.id;
            const isActive = type.status === "active";
            const isUpcoming = type.status === "upcoming";

            return (
              <motion.button
                key={type.id}
                whileHover={!isUpcoming ? { y: -2, scale: 1.01 } : undefined}
                onClick={() => setSelectedType(type)}
                className={`group rounded-3xl border p-5 text-left transition ${isSelected ? "border-slate-900 bg-slate-900 text-white dark:border-slate-200 dark:bg-slate-100 dark:text-slate-900" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"}`}
              >
                <div className="flex items-center justify-between">
                  <div
                    className={`rounded-2xl p-2.5 ${isSelected ? "bg-white/10 text-white dark:bg-slate-900/10" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"}`}
                  >
                    <Icon size={18} />
                  </div>
                  <Badge tone={isActive ? "success" : "warning"}>
                    {isActive ? "Available" : "Upcoming"}
                  </Badge>
                </div>
                <h2 className="mt-4 text-lg font-semibold">{type.title}</h2>
                <p
                  className={`mt-2 text-sm leading-6 ${isSelected ? "text-white/80 dark:text-slate-800/80" : "text-slate-600 dark:text-slate-400"}`}
                >
                  {type.description}
                </p>
                <div className="mt-4 flex items-center gap-2 text-sm font-medium">
                  <ShieldCheck size={15} />
                  {type.version}
                </div>
              </motion.button>
            );
          })}
        </div>
      </div>

      <Card className="h-fit">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400">
          <CircleAlert size={16} />
          Selected import type
        </div>
        <h2 className="mt-4 text-2xl font-semibold text-slate-950 dark:text-slate-50">
          {selectedType?.title}
        </h2>
        <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">
          {selectedType?.description}
        </p>
        <div className="mt-6 space-y-3">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
              Validation rules
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {selectedType?.validationRules.map((rule) => (
                <Badge key={rule} tone="info">
                  {rule}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
              Formats
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {selectedType?.supportedFormats.map((format) => (
                <Badge key={format} tone="default">
                  {format}
                </Badge>
              ))}
            </div>
          </div>
        </div>
        <Button
          className="mt-6 w-full gap-2"
          onClick={handleContinue}
          disabled={selectedType?.status !== "active"}
        >
          Continue
          <ArrowRight size={16} />
        </Button>
      </Card>
    </div>
  );
}
