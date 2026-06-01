export default function FeedbackPanel({ result }) {
  if (!result) return null;

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <Panel title="Priority Fixes">
        {result.priority_fixes?.length ? (
          result.priority_fixes.slice(0, 5).map((fix, index) => (
            <div key={index} className="rounded-md border border-slate-800 p-3">
              <p className="font-medium text-white">{fix.Issue || String(fix)}</p>
              {fix["Suggested Fix"] && (
                <p className="mt-1 text-sm text-slate-400">{fix["Suggested Fix"]}</p>
              )}
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-400">No priority fixes detected.</p>
        )}
      </Panel>

      <Panel title="Defense Questions">
        {result.defense_questions?.length ? (
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-300">
            {result.defense_questions.slice(0, 6).map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400">No defense questions generated.</p>
        )}
      </Panel>

      {result.responsible_ai_warnings?.length > 0 && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/40 p-4 lg:col-span-2">
          <h2 className="mb-3 text-lg font-semibold text-amber-100">
            Responsible AI Warnings
          </h2>
          <ul className="list-disc space-y-2 pl-5 text-sm text-amber-100">
            {result.responsible_ai_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Panel({ title, children }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}
