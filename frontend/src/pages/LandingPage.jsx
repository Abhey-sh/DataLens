import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Workflow } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

const options = [
  {
    title: "Single Dataset Validation",
    description:
      "Validate one independent dataset before import to a downstream system.",
    route: "/single-upload",
    badge: "V1",
    feature: "Members-ready",
  },
  {
    title: "Migration Workspace",
    description:
      "Coordinate multi-dataset validation for complex migration initiatives.",
    route: "/migration-workspace",
    badge: "Coming Soon",
    feature: "V2.0",
    disabled: true,
  },
];

export function LandingPage() {
  return (
    <div className="space-y-8">
      <motion.section
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[32px] border border-slate-200/80 bg-white/80 p-8 shadow-[0_20px_60px_-24px_rgba(15,23,42,0.25)] backdrop-blur dark:border-slate-800 dark:bg-slate-900/70 lg:p-10"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <Badge tone="info" className="w-fit">
              Trusted by ops and data teams
            </Badge>
            <h1 className="text-4xl font-semibold tracking-tight text-slate-950 dark:text-slate-50 sm:text-5xl">
              Validate imports with clarity before they touch your production
              systems.
            </h1>
            <p className="max-w-xl text-lg text-slate-600 dark:text-slate-400">
              DataLens helps teams catch broken headers, invalid values, and
              business-rule issues with a calm, enterprise-grade workflow.
            </p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-700 dark:bg-slate-950/70">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-300">
              <Workflow size={16} />
              4-step workflow
            </div>
            <div className="mt-2 text-2xl font-semibold text-slate-950 dark:text-slate-50">
              Live validation engine
            </div>
          </div>
        </div>
      </motion.section>

      <div className="grid gap-5 lg:grid-cols-2">
        {options.map((option) => (
          <Card key={option.title} hover>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
                  {option.feature}
                </p>
                <h2 className="mt-2 text-xl font-semibold text-slate-950 dark:text-slate-50">
                  {option.title}
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-400">
                  {option.description}
                </p>
              </div>
              <Badge tone={option.disabled ? "warning" : "success"}>
                {option.badge}
              </Badge>
            </div>
            <div className="mt-6 flex items-center justify-between">
              {option.disabled ? (
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  Coming soon
                </span>
              ) : (
                <Link to={option.route}>
                  <Button variant="primary" className="gap-2">
                    Launch flow
                    <ArrowRight size={16} />
                  </Button>
                </Link>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Card className="flex flex-col gap-4 border-slate-200/80 bg-slate-900 text-white dark:border-slate-700 dark:bg-slate-950">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-white/10 p-2.5">
            <Sparkles size={18} />
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-slate-400">
              Platform intelligence
            </p>
            <h3 className="text-xl font-semibold">
              Built for high-volume imports and sensitive data review.
            </h3>
          </div>
        </div>
        <p className="max-w-3xl text-sm leading-7 text-slate-300">
          The flow gives teams confidence through structured validation, guided
          review, and export-ready results without sacrificing clarity or
          control.
        </p>
      </Card>
    </div>
  );
}
