export default function SectionReviewCards({ sections = [] }) {
  if (!sections.length) return null;

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold text-white">Section Review</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {sections.map((section) => (
          <article
            key={section.section_name}
            className="rounded-lg border border-slate-800 bg-slate-900 p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">
                  {section.section_name}
                </h3>
                <p className="text-sm text-slate-400">
                  Predicted: {section.predicted_section}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xl font-semibold text-white">
                  {Number(section.defense_score || 0).toFixed(2)}
                </p>
                <p className="text-xs text-slate-500">{section.risk_level} risk</p>
              </div>
            </div>

            <p className="mt-3 text-sm leading-6 text-slate-300">
              {section.plain_language_diagnosis}
            </p>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  Strong Areas
                </p>
                {section.strong_areas?.slice(0, 3).map((area) => (
                  <span
                    key={area}
                    className="mb-2 mr-2 inline-block rounded-full bg-emerald-950 px-2 py-1 text-xs text-emerald-200"
                  >
                    {area}
                  </span>
                ))}
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  Needs Improvement
                </p>
                {section.needs_improvement_areas?.slice(0, 3).map((area) => (
                  <span
                    key={area}
                    className="mb-2 mr-2 inline-block rounded-full bg-amber-950 px-2 py-1 text-xs text-amber-200"
                  >
                    {area}
                  </span>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
