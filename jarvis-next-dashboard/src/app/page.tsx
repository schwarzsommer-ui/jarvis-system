"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Float, MeshDistortMaterial, OrbitControls, Stars } from "@react-three/drei";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  Cpu,
  Database,
  Gauge,
  GitBranch,
  Globe,
  MemoryStick,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wifi,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";

const fallbackData = {
  status: {
    online: true,
    health: "HEALTHY",
    model: "Qwen3",
    time: "--:--:--",
    energy: 96.4,
  },
  agents: [
    { name: "Commander Agent", status: "planning", hue: "cyan" },
    { name: "Coding Agent", status: "executing", hue: "blue" },
    { name: "Browser Agent", status: "active", hue: "violet" },
    { name: "Research Agent", status: "monitoring", hue: "teal" },
    { name: "Trading Agent", status: "syncing", hue: "amber" },
    { name: "Memory Agent", status: "learning", hue: "purple" },
    { name: "Tool Hunter Agent", status: "online", hue: "cyan" },
  ],
  tasks: [
    { label: "Objective", value: "Complete mission recovery pipeline", tone: "cyan" },
    { label: "Current focus", value: "Research + code + browser orchestration", tone: "violet" },
    { label: "Risk level", value: "Low / adaptive response", tone: "green" },
  ],
  logs: [
    "Commander packet synchronized",
    "Model routing: DeepSeek → planning layer",
    "Browser automation queue updated",
    "Knowledge graph refreshed with 18 new artifacts",
    "Trading monitor scanned XAUUSD and crypto spread",
  ],
  news: [
    { title: "AI infrastructure remains resilient as model latency falls", tag: "AI" },
    { title: "Global markets show renewed risk appetite in tech and energy", tag: "Markets" },
    { title: "Open-source agents accelerate local automation demand", tag: "Automation" },
  ],
  markets: [
    { symbol: "XAUUSD", value: "2349.12", change: "+0.84%", positive: true },
    { symbol: "EUR/USD", value: "1.0854", change: "+0.21%", positive: true },
    { symbol: "BTC/USD", value: "$68,420", change: "+2.31%", positive: true },
    { symbol: "NVDA", value: "$121.84", change: "-0.39%", positive: false },
  ],
  tools: [
    { name: "Ollama", status: "Connected" },
    { name: "Open WebUI", status: "Online" },
    { name: "GitHub MCP", status: "Synced" },
    { name: "Qdrant", status: "Ready" },
    { name: "n8n", status: "Listening" },
    { name: "Supabase", status: "Configured" },
  ],
  intelligence: [
    { label: "Reasoning", value: 92 },
    { label: "Planning", value: 88 },
    { label: "Autonomy", value: 94 },
    { label: "Learning", value: 90 },
  ],
  memoryNodes: [
    { x: "50%", y: "18%", label: "Goals" },
    { x: "20%", y: "48%", label: "Project" },
    { x: "78%", y: "46%", label: "Tools" },
    { x: "50%", y: "72%", label: "Memory" },
    { x: "32%", y: "82%", label: "Docs" },
    { x: "68%", y: "82%", label: "Acts" },
  ],
};

function SearchIcon(props: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="11" cy="11" r="6" />
      <path d="M16 16L21 21" />
    </svg>
  );
}

function OrbScene() {
  return (
    <Canvas camera={{ position: [0, 0, 4.2], fov: 50 }}>
      <ambientLight intensity={1.4} />
      <pointLight position={[0, 0, 3]} color="#67e8f9" intensity={24} />
      <pointLight position={[1.5, -1.2, 2]} color="#8b5cf6" intensity={18} />
      <Float speed={1.8} rotationIntensity={1.2} floatIntensity={1.4}>
        <mesh>
          <icosahedronGeometry args={[1.32, 2]} />
          <MeshDistortMaterial
            color="#5ee7ff"
            emissive="#4eaaff"
            emissiveIntensity={1.5}
            roughness={0.15}
            metalness={0.7}
            distort={0.5}
            speed={2}
          />
        </mesh>
      </Float>
      <Stars radius={26} depth={20} count={2200} factor={4} saturation={0} fade speed={1.1} />
      <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.7} />
    </Canvas>
  );
}

const renderAgentIcon = (type: string): LucideIcon => {
  switch (type) {
    case "brain":
      return BrainCircuit;
    case "cpu":
      return Cpu;
    case "globe":
      return Globe;
    case "search":
      return SearchIcon as unknown as LucideIcon;
    case "trend":
      return TrendingUp;
    case "memory":
      return MemoryStick;
    case "branch":
      return GitBranch;
    default:
      return Activity;
  }
};

export default function Home() {
  const [system, setSystem] = useState(fallbackData);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        const data = await response.json();
        setSystem(data);
      } catch {
        setSystem(fallbackData);
      }
    };

    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  const timeLabel = useMemo(() => system.status.time || "--:--:--", [system.status.time]);

  const handleCommand = async (action: string) => {
    try {
      await fetch("/api/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
    } catch {
      // Local best-effort command dispatch
    }
  };

  return (
    <main className="jarvis-page min-h-screen px-4 py-5 text-white lg:px-8">
      <motion.div
        className="jarvis-shell mx-auto flex max-w-[1600px] flex-col gap-4 rounded-[28px] border border-white/10 bg-slate-950/70 p-4 shadow-[0_0_80px_rgba(8,145,178,0.18)] backdrop-blur-xl"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <motion.header
          className="glass-panel flex items-center justify-between gap-4 rounded-[22px] border border-cyan-400/20 bg-slate-900/60 px-5 py-4"
          whileHover={{ y: -1.5 }}
          transition={{ duration: 0.2 }}
        >
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-400/10 text-cyan-300 shadow-[0_0_30px_rgba(34,211,238,0.35)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[0.62rem] uppercase tracking-[0.35em] text-cyan-300/80">AI OPERATING SYSTEM</div>
              <div className="mt-1 flex items-center gap-2 text-xl font-semibold tracking-[0.18em] text-slate-100">JARVIS</div>
            </div>
          </div>

          <div className="hidden items-center gap-6 md:flex">
            <div className="status-pill">
              <span className="status-dot" />
              {system.status.online ? "ONLINE" : "OFFLINE"}
            </div>
            <div className="mini-stat">
              <span className="label">TIME</span>
              <strong>{timeLabel}</strong>
            </div>
            <div className="mini-stat">
              <span className="label">SYSTEM</span>
              <strong>{system.status.health}</strong>
            </div>
            <div className="mini-stat">
              <span className="label">MODEL</span>
              <strong>{system.status.model}</strong>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => handleCommand("deploy")}>
              Deploy
            </Button>
            <Button size="sm" onClick={() => handleCommand("sync")}>
              Sync
            </Button>
          </div>
        </motion.header>

        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
          <motion.aside
            className="glass-panel rounded-[22px] border border-white/10 bg-slate-900/60 p-4"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.45, ease: "easeOut", delay: 0.08 }}
          >
            <div className="section-head">
              <span className="eyebrow">Active Agents</span>
              <Activity className="h-4 w-4 text-cyan-300" />
            </div>

            <div className="mt-4 space-y-3">
              {system.agents.map(({ name, status, hue }: { name: string; status: string; hue: string }, index: number) => {
                const Icon = renderAgentIcon(
                  hue === "teal" ? "search" : hue === "amber" ? "trend" : hue === "purple" ? "memory" : hue === "blue" ? "cpu" : hue === "violet" ? "globe" : hue === "cyan" ? "brain" : "branch",
                );
                const isCommander = index === 0;
                return (
                  <motion.div
                    key={name}
                    className={`agent-card ${isCommander ? "agent-card--highlight" : ""}`}
                    whileHover={{ scale: 1.01, x: 2 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="agent-info">
                      <div className={`agent-icon ${hue}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-100">{name}</div>
                        <div className="text-[0.62rem] uppercase tracking-[0.22em] text-slate-400">{status}</div>
                      </div>
                    </div>
                    <div className={`signal ${hue}`} />
                  </motion.div>
                );
              })}
            </div>
          </motion.aside>

          <motion.section
            className="glass-panel rounded-[22px] border border-cyan-400/20 bg-slate-900/55 p-4"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut", delay: 0.12 }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="eyebrow text-cyan-300">Core Objective</div>
                <h1 className="mt-2 text-2xl font-semibold text-slate-50 md:text-4xl">Autonomous mission orchestration</h1>
              </div>
              <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-[0.62rem] uppercase tracking-[0.24em] text-cyan-200">
                Live mode
              </div>
            </div>

            <div className="core-grid mt-4 grid flex-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="core-stage relative overflow-hidden rounded-[26px] border border-cyan-400/20 bg-[radial-gradient(circle_at_center,_rgba(56,189,248,0.18),_rgba(2,6,23,0.92)_52%)] p-4">
                <div className="orb-halo" />
                <div className="orb-ring orb-ring-one" />
                <div className="orb-ring orb-ring-two" />
                <div className="orb-ring orb-ring-three" />
                <div className="orb-scene">
                  <OrbScene />
                </div>
                <div className="absolute bottom-5 left-5 right-5 flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-950/35 px-3 py-2 backdrop-blur-md">
                  <span className="flex items-center gap-2 text-[0.62rem] uppercase tracking-[0.28em] text-slate-300">
                    <Zap className="h-3.5 w-3.5 text-cyan-300" />
                    Energy
                  </span>
                  <span className="text-xl font-semibold text-cyan-200">{system.status.energy ?? 96.4}%</span>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="rounded-[22px] border border-white/10 bg-slate-950/40 p-4">
                  <div className="section-head mb-3">
                    <span className="eyebrow">Current Status</span>
                    <Wifi className="h-4 w-4 text-emerald-300" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {system.tasks.map((item: { label: string; value: string; tone: string }) => (
                      <motion.div
                        key={item.label}
                        className="metric-card"
                        whileHover={{ y: -2 }}
                        transition={{ duration: 0.2 }}
                      >
                        <div className="text-[0.6rem] uppercase tracking-[0.22em] text-slate-300">{item.label}</div>
                        <div className={`mt-2 text-sm font-medium ${item.tone === "cyan" ? "text-cyan-200" : item.tone === "violet" ? "text-violet-200" : "text-emerald-200"}`}>
                          {item.value}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[22px] border border-cyan-400/20 bg-cyan-400/5 p-4">
                  <div className="section-head mb-3">
                    <span className="eyebrow">Active Thought</span>
                    <BrainCircuit className="h-4 w-4 text-cyan-300" />
                  </div>
                  <p className="text-sm leading-6 text-slate-200">
                    Planning the next autonomous chain: research the missing dependency, validate tool availability, then execute and verify the result before finalizing.
                  </p>
                </div>
              </div>
            </div>
          </motion.section>

          <motion.aside
            className="glass-panel rounded-[22px] border border-white/10 bg-slate-900/60 p-4"
            initial={{ opacity: 0, x: 18 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.45, ease: "easeOut", delay: 0.16 }}
          >
            <div className="section-head">
              <span className="eyebrow">Live Tasks</span>
              <Gauge className="h-4 w-4 text-violet-300" />
            </div>

            <div className="mt-4 space-y-3">
              {system.logs.map((entry: string, index: number) => (
                <div key={entry} className="log-row">
                  <span className="log-index">0{index + 1}</span>
                  <span className="log-text">{entry}</span>
                </div>
              ))}
            </div>

            <div className="mt-4 rounded-[18px] border border-violet-400/20 bg-violet-500/5 p-3">
              <div className="flex items-center justify-between text-xs uppercase tracking-[0.24em] text-violet-200/80">
                <span>Tool execution</span>
                <ArrowUpRight className="h-3.5 w-3.5" />
              </div>
              <div className="mt-3 text-2xl font-semibold text-violet-100">14/18</div>
              <div className="mt-2 h-2 rounded-full bg-white/5">
                <div className="h-full w-[78%] rounded-full bg-gradient-to-r from-violet-400 via-cyan-400 to-emerald-300" />
              </div>
            </div>

            <div className="mt-4 rounded-[18px] border border-white/10 bg-slate-950/30 p-3">
              <div className="section-head mb-3">
                <span className="eyebrow">Live Services</span>
                <ShieldCheck className="h-4 w-4 text-emerald-300" />
              </div>
              <div className="space-y-2">
                {system.tools.slice(0, 5).map((tool: { name: string; status: string }) => (
                  <div key={tool.name} className="flex items-center justify-between rounded-xl border border-white/5 bg-white/3 px-2.5 py-2">
                    <span className="text-[0.68rem] uppercase tracking-[0.18em] text-slate-300">{tool.name}</span>
                    <span className={`text-[0.6rem] uppercase tracking-[0.2em] ${tool.status === "Offline" ? "text-rose-300" : tool.status === "Auth required" ? "text-amber-300" : "text-emerald-300"}`}>
                      {tool.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.aside>
        </div>

        <section className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-5">
          {[
            {
              title: "News Monitoring",
              icon: ShieldCheck,
              body: system.news.map((item: { title: string; tag: string }) => (
                <div key={item.title} className="news-item">
                  <span className="news-tag">{item.tag}</span>
                  <span className="news-title">{item.title}</span>
                </div>
              )),
            },
            {
              title: "Market Monitoring",
              icon: TrendingUp,
              body: system.markets.map((market: { symbol: string; value: string; change: string; positive: boolean }) => (
                <div key={market.symbol} className="market-row">
                  <div>
                    <div className="text-sm font-medium text-slate-100">{market.symbol}</div>
                    <div className="text-[0.62rem] uppercase tracking-[0.22em] text-slate-400">Live feed</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-slate-100">{market.value}</div>
                    <div className={`text-[0.62rem] uppercase tracking-[0.22em] ${market.positive ? "text-emerald-300" : "text-rose-300"}`}>
                      {market.change}
                    </div>
                  </div>
                </div>
              )),
            },
            {
              title: "Memory Graph",
              icon: Database,
              body: (
                <div className="memory-graph mt-4">
                  <div className="graph-line line-a" />
                  <div className="graph-line line-b" />
                  <div className="graph-line line-c" />
                  <div className="graph-line line-d" />
                  {system.memoryNodes.map((node: { x: string; y: string; label: string }) => (
                    <div key={node.label} className="memory-node" style={{ left: node.x, top: node.y }}>
                      {node.label}
                    </div>
                  ))}
                </div>
              ),
            },
            {
              title: "Tool Center",
              icon: Bot,
              body: system.tools.map((tool: { name: string; status: string }) => (
                <div key={tool.name} className="tool-row">
                  <span>{tool.name}</span>
                  <span className="tool-status">{tool.status}</span>
                </div>
              )),
            },
            {
              title: "System Intelligence",
              icon: Cpu,
              body: system.intelligence.map((metric: { label: string; value: number }) => (
                <div key={metric.label}>
                  <div className="mb-1 flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-300">
                    <span>{metric.label}</span>
                    <span>{metric.value}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400"
                      style={{ width: `${metric.value}%` }}
                    />
                  </div>
                </div>
              )),
            },
          ].map(({ title, icon: Icon, body }) => (
            <motion.div
              key={title}
              className="glass-panel rounded-[22px] border border-white/10 bg-slate-900/60 p-4"
              whileHover={{ y: -2, scale: 1.005 }}
              transition={{ duration: 0.2 }}
            >
              <div className="section-head">
                <span className="eyebrow">{title}</span>
                <Icon className="h-4 w-4 text-cyan-300" />
              </div>
              <div className="mt-3 space-y-3">{body}</div>
            </motion.div>
          ))}
        </section>
      </motion.div>
    </main>
  );
}
