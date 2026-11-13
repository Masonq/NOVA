import { useEffect, useState } from "react";
import { api } from "./api.js";
import { startJob, useActiveJobs } from "./jobs.js";
import { toast } from "./ui/Toast.jsx";

/** State shared by every studio: running job of this kind, the latest result and recent works. */
export function useStudio(kind, reloadMe) {
  const [recent, setRecent] = useState([]);
  const [current, setCurrent] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => api("/api/jobs?limit=40").then((r) => {
    const mine = r.filter((j) => j.kind === kind);
    setRecent(mine.filter((j) => j.status === "done"));
    setCurrent((c) => c || mine.find((j) => j.status === "done") || null);
  }).catch(() => {});
  useEffect(() => { load(); }, []);
  const active = useActiveJobs((fin) => {
    if (fin?.kind !== kind) return;
    if (fin.status === "done") setCurrent(fin);
    reloadMe?.(); load();
  }).filter((j) => j.kind === kind);
  const run = async (prompt, params) => {
    if (busy) return;
    setBusy(true);
    try { await startJob(kind, prompt, params); reloadMe?.(); }
    catch (e) { toast(e.message, "error"); }
    finally { setBusy(false); }
  };
  return { active: active[0], recent, current, setCurrent, run, busy, reload: load };
}
