export default function TextInputPanel({
  mode,
  text,
  onTextChange,
  file,
  onFileChange,
  onSubmit,
  loading
}) {
  const label =
    mode === "manuscript"
      ? "Paste full thesis manuscript or large chapter text"
      : "Paste thesis section text";

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Thesis Input</h2>
          <p className="text-sm text-slate-400">
            Upload a document or paste text directly. Uploaded files take priority.
          </p>
        </div>
        <input
          type="file"
          accept=".txt,.docx,.pdf"
          onChange={(event) => onFileChange(event.target.files?.[0] || null)}
          className="block w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-cyan-500 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-950 md:w-96"
        />
      </div>

      {file && (
        <div className="mb-3 rounded-md border border-cyan-900 bg-cyan-950/40 px-3 py-2 text-sm text-cyan-100">
          Selected file: {file.name}
        </div>
      )}

      <label className="mb-2 block text-sm font-medium text-slate-200">
        {label}
      </label>
      <textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        rows={12}
        placeholder="Paste thesis text here..."
        className="w-full resize-y rounded-md border border-slate-700 bg-slate-950 p-3 text-sm leading-6 text-slate-100 outline-none focus:border-cyan-500"
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={loading}
        className="mt-4 w-full rounded-md bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Analyzing..." : mode === "manuscript" ? "Analyze Full Manuscript" : "Analyze Section"}
      </button>
    </section>
  );
}
