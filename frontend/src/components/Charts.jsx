import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

export function SectionScoreChart({ rows = [] }) {
  if (!rows.length) return null;

  const data = rows.map((row) => ({
    name: row["Section Name"],
    score: Number(row["Defense Score"] || 0)
  }));

  return (
    <ChartShell title="Defense Readiness Score per Section">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 100]} stroke="#94a3b8" />
          <Tooltip />
          <Bar dataKey="score" fill="#22d3ee" />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export function EvidenceChart({ rows = [] }) {
  if (!rows.length) return null;

  const data = rows.slice(0, 8).map((row) => ({
    name: row["Evidence Area"],
    score: Number(row["Similarity Score"] || 0)
  }));

  return (
    <ChartShell title="Semantic Evidence Coverage Scores">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 1]} stroke="#94a3b8" />
          <Tooltip />
          <Bar dataKey="score" fill="#34d399" />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export function AlignmentChart({ rows = [] }) {
  const data = rows
    .filter((row) => row["Similarity Score"] != null)
    .map((row) => ({
      name: row["Section Pair"],
      score: Number(row["Similarity Score"])
    }));

  if (!data.length) return null;

  return (
    <ChartShell title="Semantic Alignment Between Thesis Sections">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 1]} stroke="#94a3b8" />
          <Tooltip />
          <Bar dataKey="score" fill="#f59e0b" />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export function EvaluationCharts({ rows = [] }) {
  if (!rows.length) return null;

  const scoreData = rows.map((row) => ({
    name: row.sample_id,
    manual: Number(row.manual_score || 0),
    system: Number(row.system_score || 0)
  }));
  const timeData = rows.map((row) => ({
    name: row.sample_id,
    seconds: Number(row.processing_time_seconds || 0)
  }));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartShell title="Manual Score vs System Score">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={scoreData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="name" stroke="#94a3b8" />
            <YAxis domain={[0, 100]} stroke="#94a3b8" />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="manual" stroke="#f59e0b" />
            <Line type="monotone" dataKey="system" stroke="#22d3ee" />
          </LineChart>
        </ResponsiveContainer>
      </ChartShell>
      <ChartShell title="Processing Time per Sample">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={timeData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="name" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip />
            <Bar dataKey="seconds" fill="#a78bfa" />
          </BarChart>
        </ResponsiveContainer>
      </ChartShell>
    </div>
  );
}

function ChartShell({ title, children }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">{title}</h2>
      {children}
    </section>
  );
}
