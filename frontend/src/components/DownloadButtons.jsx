const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function DownloadButtons({ reportFilename, resultsFilename }) {
  if (!reportFilename && !resultsFilename) return null;

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Downloads</h2>
      <div className="flex flex-wrap gap-3">
        {reportFilename && (
          <a
            href={`${API_BASE}/download-report/${reportFilename}`}
            className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400"
          >
            Download PDF Report
          </a>
        )}
        {resultsFilename && (
          <a
            href={`${API_BASE}/download-report/${resultsFilename}`}
            className="rounded-md bg-slate-700 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-600"
          >
            Download CSV Results
          </a>
        )}
      </div>
    </section>
  );
}
