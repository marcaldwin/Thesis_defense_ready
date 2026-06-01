const modes = [
  { id: "section", label: "Single Section" },
  { id: "manuscript", label: "Full Manuscript" },
  { id: "compare", label: "Compare Revisions" },
  { id: "evaluation", label: "Evaluation Dataset" }
];

export default function ModeSelector({ mode, onChange }) {
  return (
    <div className="grid gap-2 rounded-lg border border-slate-800 bg-slate-900 p-2 sm:grid-cols-4">
      {modes.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={`rounded-md px-3 py-2 text-sm font-medium transition ${
            mode === item.id
              ? "bg-cyan-500 text-slate-950"
              : "bg-slate-950 text-slate-300 hover:bg-slate-800"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
