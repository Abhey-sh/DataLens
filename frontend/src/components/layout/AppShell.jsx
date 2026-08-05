import { motion } from "framer-motion";
import { Home, Moon, ShieldCheck, Sparkles, Sun } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { Button } from "../ui/Button";
import { useTheme } from "../../context/ThemeContext";

const links = [
  { label: "Home", href: "/", icon: Home },
  { label: "Validate", href: "/single-upload", icon: ShieldCheck },
];

export function AppShell() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.03),_transparent_45%)] text-slate-900 transition-colors dark:bg-[radial-gradient(circle_at_top_left,_rgba(148,163,184,0.12),_transparent_45%)] dark:text-slate-100">
      <header className="mx-auto flex max-w-7xl items-center justify-between border-b border-slate-200/80 px-6 py-5 lg:px-8 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg dark:bg-slate-100 dark:text-slate-950">
            <Sparkles size={20} />
          </div>
          <div>
            <p className="text-lg font-semibold">DataLens</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Enterprise data validation
            </p>
          </div>
        </div>
        <nav className="hidden items-center gap-2 md:flex">
          {links.map(({ label, href, icon: Icon }) => (
            <NavLink
              key={href}
              to={href}
              className={({ isActive }) =>
                (isActive
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100") +
                " rounded-full px-4 py-2 text-sm font-medium transition"
              }
            >
              <span className="flex items-center gap-2">
                <Icon size={16} />
                {label}
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <Button variant="secondary" className="hidden sm:inline-flex">
            Book a demo
          </Button>
          <button
            type="button"
            onClick={toggleTheme}
            className="rounded-full border border-slate-200 bg-white p-2.5 text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            aria-label="Toggle color theme"
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      <motion.main
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto max-w-7xl px-6 py-8 lg:px-8"
      >
        <Outlet />
      </motion.main>
    </div>
  );
}
