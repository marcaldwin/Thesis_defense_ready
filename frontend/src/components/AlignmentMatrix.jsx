export default function AlignmentMatrix({ rows = [] }) {
  if (!rows.length) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
        Semantic alignment data appears after Full Manuscript analysis.
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Semantic Alignment Matrix</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Section Pair</th>
              <th className="px-3 py-2">Similarity</th>
              <th className="px-3 py-2">Level</th>
              <th className="px-3 py-2">Risk</th>
              <th className="px-3 py-2">Interpretation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {rows.map((row) => (
              <tr key={row["Section Pair"]}>
                <td className="px-3 py-3 text-slate-100">{row["Section Pair"]}</td>
                <td className="px-3 py-3 text-slate-300">
                  {row["Similarity Score"] == null
                    ? "N/A"
                    : Number(row["Similarity Score"]).toFixed(2)}
                </td>
                <td className="px-3 py-3 text-slate-300">{row["Alignment Level"]}</td>
                <td className="px-3 py-3 text-slate-300">{row.Risk}</td>
                <td className="px-3 py-3 text-slate-400">{row.Interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
