function cardClass(risk) {
  if (risk === "Low") return "border-emerald-800 bg-emerald-950/40";
  if (risk === "Moderate") return "border-amber-800 bg-amber-950/40";
  if (risk === "High") return "border-rose-800 bg-rose-950/40";
  return "border-slate-800 bg-slate-900";
}

export default function ScoreCards({ result }) {
  if (!result) return null;

  const score = result.overall_score ?? result.defense_score;
  const risk = result.overall_risk_level ?? result.risk_level;

  return (
    <section className="grid gap-3 md:grid-cols-4">
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-xs uppercase tracking-wide text-slate-500">Detected Section</p>
        <p className="mt-2 text-xl font-semibold text-white">
          {result.predicted_section || "Not available"}
        </p>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-xs uppercase tracking-wide text-slate-500">Readiness Score</p>
        <p className="mt-2 text-2xl font-semibold text-white">
          {Number(score || 0).toFixed(2)}/100
        </p>
      </div>
      <div className={`rounded-lg border p-4 ${cardClass(risk)}`}>
        <p className="text-xs uppercase tracking-wide text-slate-400">Risk Level</p>
        <p className="mt-2 text-xl font-semibold text-white">{risk || "Not available"}</p>
      </div>
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <p className="text-xs uppercase tracking-wide text-slate-500">Processing Time</p>
        <p className="mt-2 text-xl font-semibold text-white">
          {result.processing_time_seconds ? `${result.processing_time_seconds}s` : "N/A"}
        </p>
      </div>
    </section>
  );
}
