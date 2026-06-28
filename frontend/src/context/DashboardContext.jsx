/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { createSocket } from "@/services/socket";

const API = import.meta.env.VITE_API_URL || ""; // empty = relative to current origin

const DashboardContext = createContext(null);

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within <DashboardProvider>");
  return ctx;
}

/*
 * DashboardProvider — single home for every piece of CCE dashboard logic.
 * The old monolithic Dashboard.jsx kept all of this inline; splitting the UI
 * into routed pages, we lift the state/effects/handlers here so there is still
 * exactly ONE WebSocket and ONE source of truth, and pages stay presentational.
 * All fetch/animation behaviour is ported verbatim.
 */
export function DashboardProvider({ token: propToken, onLogout, children }) {
  const [token] = useState(propToken || "");
  const [connected, setConnected] = useState(false);
  const [liveEvents, setLiveEvents] = useState([]);

  const [simTrace, setSimTrace] = useState([]);
  const [simSummary, setSimSummary] = useState(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simError, setSimError] = useState("");
  const [metrics, setMetrics] = useState(null);

  const [ablation, setAblation] = useState(null);
  const [ablationRunning, setAblationRunning] = useState(false);

  const [conflictResult, setConflictResult] = useState(null);
  const [replayResult, setReplayResult] = useState(null);

  const [csi, setCsi] = useState(null);
  const [, setTrustCurve] = useState([]);

  const [singleRunHistory, setSingleRunHistory] = useState([]);
  const [singleRunInput, setSingleRunInput] = useState({
    task_name: "infra-task",
    observed_latency: 110,
    cpu_utilisation: 0.75,
    error_rate: 0.0,
  });
  const [singleRunning, setSingleRunning] = useState(false);
  const [singleRunError, setSingleRunError] = useState("");
  const [windowSize, setWindowSize] = useState(0);
  const [resetting, setResetting] = useState(false);

  const socketRef = useRef(null);
  const animRef = useRef(null);

  // ── websocket ──
  useEffect(() => {
    const socket = createSocket();
    socketRef.current = socket;
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.event === "task_completed") {
          setLiveEvents((prev) => [data, ...prev].slice(0, 50));
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => socket.close();
  }, []);

  async function runAblation() {
    if (!token) return;
    setAblationRunning(true);
    setAblation(null);
    try {
      const res = await fetch(`${API}/tasks/ablation`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ steps: [{ observed_latency: 80 }] }),
      });
      if (res.ok) {
        const data = await res.json();
        setAblation(data);
      }
    } catch (e) {
      console.error("Ablation failed", e);
    }
    setAblationRunning(false);
  }

  async function runSimulation() {
    if (!token) {
      setSimError("Paste your JWT token first.");
      return;
    }
    setSimError("");
    setSimRunning(true);
    setSimTrace([]);
    setSimSummary(null);

    const steps = [
      ...Array(10).fill({ observed_latency: 30, cpu_utilisation: 0.2, error_rate: 0.0 }),
      ...Array(10).fill({ observed_latency: 130, cpu_utilisation: 0.85, error_rate: 0.05 }),
      ...Array(5).fill({ observed_latency: 30, cpu_utilisation: 0.2, error_rate: 0.0 }),
      ...Array(5).fill({ observed_latency: 130, cpu_utilisation: 0.85, error_rate: 0.05 }),
    ];

    try {
      const res = await fetch(`${API}/tasks/simulate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ steps }),
      });

      if (!res.ok) {
        const err = await res.json();
        setSimError(`API error ${res.status}: ${JSON.stringify(err.detail)}`);
        setSimRunning(false);
        return;
      }

      const data = await res.json();
      setSimSummary(data.summary);
      if (data.csi) setCsi(data.csi);
      if (data.trust_curve) setTrustCurve(data.trust_curve);

      // animate trace step by step
      let i = 0;
      animRef.current = setInterval(() => {
        setSimTrace((prev) => [...prev, data.trace[i]]);
        i++;
        if (i >= data.trace.length) {
          clearInterval(animRef.current);
          setSimRunning(false);
          fetchMetrics();
        }
      }, 80);
    } catch (e) {
      setSimError(`Network error: ${e.message}`);
      setSimRunning(false);
    }
  }

  async function fetchHistory() {
    if (!token) return;
    try {
      const res = await fetch(`${API}/tasks/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSingleRunHistory(data); // oldest-first (id asc)
      }
    } catch {
      /* non-fatal: leave state unchanged */
    }
  }

  async function resetSupervisor() {
    if (!token) return;
    setResetting(true);
    try {
      await fetch(`${API}/tasks/reset`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setWindowSize(0);
      setSingleRunHistory([]);
    } catch {
      /* non-fatal: leave state unchanged */
    }
    setResetting(false);
  }

  async function runSingleStep() {
    if (!token) {
      setSingleRunError("Token required.");
      return;
    }
    setSingleRunning(true);
    setSingleRunError("");
    try {
      const res = await fetch(`${API}/tasks/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          task_name: singleRunInput.task_name,
          observed_latency: Number(singleRunInput.observed_latency),
          cpu_utilisation: Number(singleRunInput.cpu_utilisation),
          error_rate: Number(singleRunInput.error_rate),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setSingleRunError(`API error ${res.status}: ${JSON.stringify(err.detail)}`);
        setSingleRunning(false);
        return;
      }
      const data = await res.json();
      const r = data.result;
      const newEntry = {
        id: data.task_id,
        task_name: singleRunInput.task_name,
        final_intent: r.final_intent,
        trust_score: r.trust_score,
        reason: r.reason,
        observed_latency: Number(singleRunInput.observed_latency),
        conflict: r.conflict ?? false,
        capacity_agent: r.capacity_agent ?? null,
        network_agent: r.network_agent ?? null,
      };
      setSingleRunHistory((prev) => [...prev, newEntry]);
      setWindowSize(r.window_size ?? 0);
      fetchMetrics();
    } catch (e) {
      setSingleRunError(`Network error: ${e.message}`);
    }
    setSingleRunning(false);
  }

  async function fetchMetrics() {
    if (!token) return;
    try {
      const res = await fetch(`${API}/tasks/metrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch {
      /* non-fatal: leave state unchanged */
    }
  }

  useEffect(() => () => clearInterval(animRef.current), []);

  // load metrics + history on mount / token change
  useEffect(() => {
    (async () => {
      await fetchMetrics();
      await fetchHistory();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // chart data derived from the animated sim trace
  const chartData = simTrace.map((s) => ({
    step: s.step,
    latency: s.observed_latency,
    trust: s.trust_score,
    decayed_trust: s.decayed_trust,
  }));

  const value = {
    API,
    token,
    onLogout,
    connected,
    liveEvents,
    simTrace,
    simSummary,
    simRunning,
    simError,
    metrics,
    ablation,
    ablationRunning,
    conflictResult,
    setConflictResult,
    replayResult,
    setReplayResult,
    csi,
    singleRunHistory,
    singleRunInput,
    setSingleRunInput,
    singleRunning,
    singleRunError,
    windowSize,
    resetting,
    chartData,
    runSimulation,
    runAblation,
    runSingleStep,
    resetSupervisor,
    fetchMetrics,
    fetchHistory,
    setSingleRunError,
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}
