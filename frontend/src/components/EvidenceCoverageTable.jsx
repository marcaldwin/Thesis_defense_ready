function levelClass(level) {
  if (level === "Strong") return "bg-emerald-950 text-emerald-200";
  if (level === "Moderate") return "bg-amber-950 text-amber-200";
  return "bg-rose-950 text-rose-200";
}

export default function EvidenceCoverageTable({ rows = [] }) {
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
        No evidence coverage data available yet.
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Evidence Coverage</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Evidence Area</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">Coverage</th>
              <th className="px-3 py-2">Interpretation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {rows.map((row) => (
              <tr key={row["Evidence Area"]}>
                <td className="px-3 py-3 font-medium text-slate-100">
                  {row["Evidence Area"]}
                </td>
                <td className="px-3 py-3 text-slate-300">
                  {Number(row["Similarity Score"] || 0).toFixed(2)}
                </td>
                <td className="px-3 py-3">
                  <span className={`rounded-full px-2 py-1 text-xs ${levelClass(row["Coverage Level"])}`}>
                    {row["Coverage Level"]}
                  </span>
                </td>
                <td className="px-3 py-3 text-slate-400">{row.Interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
