import { useEffect, useState, useRef } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const TABS = [
  { id: "section", label: "Section review", description: "Check one chapter", icon: "section" },
  { id: "manuscript", label: "Full manuscript", description: "Review the whole thesis", icon: "manuscript" },
  { id: "compare", label: "Compare drafts", description: "Measure improvement", icon: "compare" },
  { id: "evaluate", label: "Dataset test", description: "Validate the model", icon: "dataset" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState("section");
  const [theme, setTheme] = useState(() => {
    const savedTheme = window.localStorage.getItem("sage-theme");
    if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  const [sectionText, setSectionText] = useState("");
  const [sectionFile, setSectionFile] = useState(null);
  const [manuscriptText, setManuscriptText] = useState("");
  const [manuscriptFile, setManuscriptFile] = useState(null);
  const [originalText, setOriginalText] = useState("");
  const [revisedText, setRevisedText] = useState("");
  const [csvFile, setCsvFile] = useState(null);

  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const prevResultRef = useRef(null);
  const activeRequestRef = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("sage-theme", theme);
  }, [theme]);

  function clearOutput(cancelActiveRequest = true) {
    if (cancelActiveRequest && activeRequestRef.current) {
      activeRequestRef.current.abort();
      activeRequestRef.current = null;
      setLoading(false);
    }
    if (result) {
      prevResultRef.current = result;
    }
    setResult(null);
    setError("");
  }

  async function callJson(path, body) {
    activeRequestRef.current?.abort();
    const controller = new AbortController();
    activeRequestRef.current = controller;
    setLoading(true);
    clearOutput(false);
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
      setResult(data);
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message || "Request failed.");
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null;
        setLoading(false);
      }
    }
  }

  async function callForm(path, formData) {
    activeRequestRef.current?.abort();
    const controller = new AbortController();
    activeRequestRef.current = controller;
    setLoading(true);
    clearOutput(false);
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        body: formData,
        signal: controller.signal
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
      setResult(data);
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message || "Request failed.");
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null;
        setLoading(false);
      }
    }
  }

  function analyzeSection() {
    if (sectionFile) {
      const fd = new FormData();
      fd.append("file", sectionFile);
      if (sectionText.trim()) fd.append("text", sectionText);
      callForm("/analyze-section", fd);
      return;
    }
    if (!sectionText.trim()) {
      setError("Paste a thesis section or upload a document first.");
      return;
    }
    callJson("/analyze-section", { text: sectionText });
  }

  function analyzeManuscript() {
    if (manuscriptFile) {
      const fd = new FormData();
      fd.append("file", manuscriptFile);
      if (manuscriptText.trim()) fd.append("text", manuscriptText);
      callForm("/analyze-full-manuscript", fd);
      return;
    }
    if (!manuscriptText.trim()) {
      setError("Paste a full manuscript or upload a document first.");
      return;
    }
    callJson("/analyze-full-manuscript", { text: manuscriptText });
  }

  function compareRevisions() {
    if (!originalText.trim() || !revisedText.trim()) {
      setError("Provide both the original and revised text.");
      return;
    }
    callJson("/compare-revisions", {
      original_text: originalText,
      revised_text: revisedText
    });
  }

  function evaluateDataset() {
    if (!csvFile) {
      setError("Choose a CSV file first.");
      return;
    }
    const fd = new FormData();
    fd.append("file", csvFile);
    callForm("/evaluate-dataset", fd);
  }

  function handleTabChange(id) {
    setActiveTab(id);
    clearOutput();
  }

  function updateSectionText(value) {
    setSectionText(value);
    clearOutput();
  }

  function updateSectionFile(value) {
    setSectionFile(value);
    clearOutput();
  }

  function updateManuscriptText(value) {
    setManuscriptText(value);
    clearOutput();
  }

  function updateManuscriptFile(value) {
    setManuscriptFile(value);
    clearOutput();
  }

  function updateOriginalText(value) {
    setOriginalText(value);
    clearOutput();
  }

  function updateRevisedText(value) {
    setRevisedText(value);
    clearOutput();
  }

  function updateCsvFile(value) {
    setCsvFile(value);
    clearOutput();
  }

  return (
    <main className="app">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">S</div>
          <div className="brand">
            <span className="brand-tag">SAGE-Review</span>
            <h1>Thesis readiness workspace</h1>
            <p className="muted">
              Find evidence gaps, strengthen your manuscript, and prepare for defense.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="theme-toggle"
          onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          aria-pressed={theme === "dark"}
        >
          <span className="theme-toggle-icon" aria-hidden="true">
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.2 15.4A8.5 8.5 0 0 1 8.6 3.8 8.5 8.5 0 1 0 20.2 15.4Z" />
              </svg>
            )}
          </span>
          <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
      </header>

      <nav className="tabs" role="tablist" aria-label="Analysis modes">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls="analysis-panel"
            className={`tab ${activeTab === tab.id ? "tab-active" : ""}`}
            onClick={() => handleTabChange(tab.id)}
          >
            <ModeIcon name={tab.icon} />
            <span className="tab-copy">
              <span className="tab-label">{tab.label}</span>
              <span className="tab-description">{tab.description}</span>
            </span>
          </button>
        ))}
      </nav>

      <section id="analysis-panel" className="panel analysis-panel" role="tabpanel">
        {activeTab === "section" && (
          <Form
            eyebrow="Focused review"
            title="Review one thesis section"
            description="Paste the section below or upload a document. You will get a readiness score and a short revision plan."
          >
            <Field label="Thesis section text">
              <textarea
                id="section-text"
                name="section_text"
                rows={12}
                value={sectionText}
                onChange={(e) => updateSectionText(e.target.value)}
                placeholder="Paste an Introduction, Methodology, Results, or Conclusion section..."
              />
            </Field>
            <Field label="Or upload a document (PDF / DOCX / TXT)">
              <input
                id="section-file"
                name="section_file"
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => updateSectionFile(e.target.files?.[0] || null)}
              />
              {sectionFile && <p className="hint">Selected: {sectionFile.name}</p>}
            </Field>
            <PrimaryButton
              loading={loading}
              onClick={analyzeSection}
              label="Analyze Section"
              loadingLabel="Analyzing section..."
            />
          </Form>
        )}

        {activeTab === "manuscript" && (
          <Form
            eyebrow="Complete review"
            title="Review your full manuscript"
            description="Upload your thesis to see section readiness, evidence coverage, and the most important fixes first."
          >
            <Field label="Full manuscript text">
              <textarea
                id="manuscript-text"
                name="manuscript_text"
                rows={12}
                value={manuscriptText}
                onChange={(e) => updateManuscriptText(e.target.value)}
                placeholder="Paste the full thesis manuscript here..."
              />
            </Field>
            <Field label="Or upload a manuscript (PDF / DOCX / TXT)">
              <input
                id="manuscript-file"
                name="manuscript_file"
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => updateManuscriptFile(e.target.files?.[0] || null)}
              />
              {manuscriptFile && (
                <p className="hint">Selected: {manuscriptFile.name}</p>
              )}
            </Field>
            <PrimaryButton
              loading={loading}
              onClick={analyzeManuscript}
              label="Analyze Full Manuscript"
              loadingLabel="Analyzing manuscript..."
            />
          </Form>
        )}

        {activeTab === "compare" && (
          <Form
            eyebrow="Revision check"
            title="Compare two drafts"
            description="See whether the revision improved evidence coverage and defense readiness."
          >
            <div className="grid-2">
              <Field label="Original">
                <textarea
                  id="original-text"
                  name="original_text"
                  rows={12}
                  value={originalText}
                  onChange={(e) => updateOriginalText(e.target.value)}
                  placeholder="Paste the original section..."
                />
              </Field>
              <Field label="Revised">
                <textarea
                  id="revised-text"
                  name="revised_text"
                  rows={12}
                  value={revisedText}
                  onChange={(e) => updateRevisedText(e.target.value)}
                  placeholder="Paste the revised section..."
                />
              </Field>
            </div>
            <PrimaryButton
              loading={loading}
              onClick={compareRevisions}
              label="Compare Revisions"
              loadingLabel="Comparing..."
            />
          </Form>
        )}

        {activeTab === "evaluate" && (
          <Form
            eyebrow="Quality assurance"
            title="Evaluate a labeled dataset"
            description="Upload a CSV to measure classification and issue-detection performance."
          >
            <Field label="Evaluation CSV">
              <input
                id="evaluation-file"
                name="evaluation_file"
                type="file"
                accept=".csv"
                onChange={(e) => updateCsvFile(e.target.files?.[0] || null)}
              />
              {csvFile && <p className="hint">Selected: {csvFile.name}</p>}
            </Field>
            <PrimaryButton
              loading={loading}
              onClick={evaluateDataset}
              label="Run Evaluation"
              loadingLabel="Running evaluation..."
            />
          </Form>
        )}
      </section>

      {error && <div className="alert alert-error" role="alert">{error}</div>}

      {result && activeTab === "manuscript" && <ManuscriptDashboard result={result} prevResult={prevResultRef.current} />}
      {result && activeTab === "section" && <SectionResultPanel result={result} prevResult={prevResultRef.current} />}
      {result && activeTab === "compare" && <CompareResultPanel result={result} />}
      {result && activeTab === "evaluate" && <EvaluateResultPanel result={result} />}


      <footer className="app-footer muted">
        SAGE-Review is a decision-support tool and does not replace adviser or
        panel judgment.
      </footer>
    </main>
  );
}

/* ───────────────────────── Input helpers ───────────────────────── */

function Form({ eyebrow, title, description, children }) {
  return (
    <div className="form">
      <div className="form-heading">
        {eyebrow && <span className="section-eyebrow">{eyebrow}</span>}
        <h2 className="panel-title">{title}</h2>
        {description && <p className="form-description">{description}</p>}
      </div>
      <div className="form-body">{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

function PrimaryButton({ loading, onClick, label, loadingLabel }) {
  return (
    <button
      type="button"
      className="btn-primary"
      onClick={onClick}
      disabled={loading}
    >
      {loading && <span className="button-spinner" aria-hidden="true" />}
      <span>{loading ? loadingLabel : label}</span>
      {!loading && <span className="button-arrow" aria-hidden="true">→</span>}
    </button>
  );
}

function ModeIcon({ name }) {
  const paths = {
    section: <><path d="M7 3.75h7l3 3V20.25H7z" /><path d="M14 3.75v3h3M10 11h4M10 14.5h4" /></>,
    manuscript: <><path d="M6 4.5h9.5a2 2 0 0 1 2 2v13H8a2 2 0 0 1-2-2z" /><path d="M8 4.5v15M11 9h3.5M11 12.5h3.5" /></>,
    compare: <><path d="M7.5 7h10M14.5 4l3 3-3 3M16.5 17h-10M9.5 14l-3 3 3 3" /></>,
    dataset: <><ellipse cx="12" cy="6" rx="6" ry="2.5" /><path d="M6 6v6c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V6M6 12v5.5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V12" /></>
  };
  return (
    <span className="mode-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        {paths[name]}
      </svg>
    </span>
  );
}

/* ───────────────────────── Shared visual atoms ───────────────────────── */

function Badge({ value, tone = "muted" }) {
  if (value == null || value === "") return null;
  return <span className={`badge badge-${tone}`}>{String(value)}</span>;
}

function ScoreCard({ label, value, tone = "" }) {
  return (
    <div className={`score-card score-${tone}`}>
      <span className="score-label">{label}</span>
      <span className="score-value">{value}</span>
    </div>
  );
}

function riskBadgeTone(value) {
  const v = String(value || "").toLowerCase();
  if (v === "low") return "ok";
  if (v === "moderate") return "warn";
  if (v === "high") return "danger";
  return "muted";
}

function confidenceBadgeTone(value) {
  const v = String(value || "").toLowerCase();
  if (v === "complete" || v === "high") return "ok";
  if (v === "partial" || v === "moderate") return "warn";
  if (v === "low") return "danger";
  return "muted";
}

function alignmentBadgeTone(value) {
  const v = String(value || "").toLowerCase();
  if (v.includes("strong")) return "ok";
  if (v.includes("moderate")) return "warn";
  if (v.includes("weak") || v.includes("missing")) return "danger";
  return "muted";
}

function coverageBadgeTone(value) {
  const v = String(value || "").toLowerCase();
  if (v === "strong") return "ok";
  if (v === "moderate") return "warn";
  if (v === "weak") return "danger";
  return "muted";
}

function coverageFill(value) {
  const v = String(value || "").toLowerCase();
  if (v === "strong") return "#3c9560";
  if (v === "moderate") return "#cf9130";
  if (v === "weak") return "#cf5656";
  return "#0f766e";
}

function evidenceScoreLabel(row) {
  if (row.display_score_label) return row.display_score_label;
  const raw = Number(row["Similarity Score"] ?? row.similarity_score ?? 0);
  const clamped = Math.max(0, Math.min(1, Number.isFinite(raw) ? raw : 0));
  return `${Math.round(clamped * 100)}%`;
}

function evidenceChartScore(row) {
  const raw = Number(row["Similarity Score"] ?? row.similarity_score ?? row.display_score ?? 0);
  return Math.max(0, Math.min(1, Number.isFinite(raw) ? raw : 0));
}

function shortenPair(pair) {
  return String(pair || "")
    .replace(" <-> ", " ↔ ")
    .replace("Objectives of the Study", "Objectives")
    .replace("Results and Discussion", "Results");
}

const CHART_TOOLTIP_STYLE = {
  background: "var(--panel)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  color: "var(--text)",
  fontSize: 12
};

/* ───────────────────────── Manuscript Dashboard ───────────────────────── */

function ManuscriptDashboard({ result, prevResult }) {
  return (
    <div className="results-dashboard">
      <ResultHeading
        title="Manuscript review"
        subtitle="Start with the priorities, then open the supporting analysis when you need it."
        result={result}
      />
      <ExecutiveSummary result={result} />
      <div className="dashboard-grid dashboard-grid-priority">
        <MainIssuesPanel
          issues={result.main_issues}
          explainedIssues={result.main_issues_explained}
          recommendedFixOrder={result.recommended_fix_order}
          extractionWarnings={result.extraction_warnings}
        />
        <HighlightsPanel
          topWeakSections={result.top_weak_sections}
          topWeakSectionsExplained={result.top_weak_sections_explained}
          topWeakAlignmentPairs={result.top_weak_alignment_pairs}
          alignmentWeaknessesExplained={result.alignment_weaknesses_explained}
        />
      </div>
      <SectionSummaryPanel sectionResults={result.section_results} />
      <EvidenceCoveragePanel result={result} isManuscript={true} prevResult={prevResult} />
      <DashboardAccordion
        title="Section-by-section review"
        description="Open detailed diagnoses, revision ideas, and scoring evidence."
      >
        <SectionDetailsPanel sections={result.section_details} />
      </DashboardAccordion>
      <DashboardAccordion
        title="Alignment and document structure"
        description="Inspect section relationships and the headings detected in the file."
      >
        <AlignmentMatrixPanel
          rows={result.raw_alignment_results?.length ? result.raw_alignment_results : result.alignment_results}
        />
        <DetectedHeadingsPanel
          majorHeadings={result.major_detected_headings || result.detected_headings}
        />
      </DashboardAccordion>
      <OverallNotesPanel notes={result.overall_defense_notes} />
      <DownloadReportPanel filename={result.report_filename} />
    </div>
  );
}

function ResultHeading({ title, subtitle, result }) {
  return (
    <section className="result-heading">
      <div>
        <span className="section-eyebrow">Analysis complete</span>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <div className="result-source" aria-label="Analysis source">
        <span className="result-source-label">Source</span>
        <strong>{result.source_filename || "Pasted text"}</strong>
        {result.analysis_timestamp && <span>{result.analysis_timestamp}</span>}
      </div>
    </section>
  );
}

function DashboardAccordion({ title, description, children }) {
  return (
    <details className="dashboard-accordion">
      <summary>
        <span className="accordion-icon" aria-hidden="true">+</span>
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <span className="accordion-action">View details</span>
      </summary>
      <div className="accordion-content">{children}</div>
    </details>
  );
}

function ExecutiveSummary({ result }) {
  const score = result.overall_score ?? result.defense_score;
  const risk = result.overall_risk_level || result.risk_level;
  const confidence = result.analysis_confidence;
  const wordCount = result.word_count;
  const processingTime = result.processing_time_seconds;
  const isIncomplete = result.result_type === "Extraction Incomplete";
  const numericScore = Number(score);
  const safeScore = Number.isFinite(numericScore)
    ? Math.max(0, Math.min(100, numericScore))
    : 0;

  const items = [
    risk && {
      label: "Defense risk",
      value: <Badge value={risk} tone={riskBadgeTone(risk)} />
    },
    confidence && {
      label: "Confidence",
      value: <Badge value={confidence} tone={confidenceBadgeTone(confidence)} />
    },
    wordCount != null && {
      label: "Words reviewed",
      value: typeof wordCount === "number" ? wordCount.toLocaleString() : wordCount
    },
    processingTime != null && {
      label: "Review time",
      value: `${processingTime}s`
    }
  ].filter(Boolean);

  return (
    <section className="panel summary-panel">
      <div className="readiness-score">
        <div
          className={`score-ring ring-${isIncomplete ? "muted" : riskBadgeTone(risk)}`}
          style={{ "--score-angle": `${safeScore * 3.6}deg` }}
          aria-label={`Readiness score ${isIncomplete ? "not reliable" : `${score} out of 100`}`}
        >
          <div className="score-ring-inner">
            <strong>{isIncomplete ? "–" : Math.round(safeScore)}</strong>
            <span>/ 100</span>
          </div>
        </div>
        <div className="readiness-copy">
          <span className="section-eyebrow">Readiness score</span>
          <h3>{isIncomplete ? "Document structure needs attention" : `${risk || "Unknown"} defense risk`}</h3>
          <p>{isIncomplete
            ? "Fix the manuscript headings before relying on the overall score."
            : "Use the priority actions below as your revision checklist."}</p>
        </div>
      </div>
      <div className="summary-stats">
        {items.map((item, i) => <ScoreCard key={i} {...item} />)}
      </div>
      {isIncomplete && result.recommendation && (
        <div className="alert alert-error summary-alert">
          <strong>{result.result_type}:</strong> {result.recommendation}
        </div>
      )}
    </section>
  );
}

function MainIssuesPanel({ issues = [], explainedIssues = [], recommendedFixOrder = [], extractionWarnings = [] }) {
  const allIssues = [
    ...(extractionWarnings || []).map((w) => ({ text: w, tone: "warn" })),
    ...(!explainedIssues.length ? (issues || []).map((w) => ({ text: w, tone: "warn" })) : [])
  ];
  if (!allIssues.length && !explainedIssues.length && !recommendedFixOrder.length) return null;
  return (
    <section className="panel priority-panel">
      <div className="panel-heading-row">
        <div>
          <span className="section-eyebrow">Needs attention</span>
          <h2 className="panel-title">Priority issues</h2>
        </div>
        <span className="count-chip">{allIssues.length + explainedIssues.length}</span>
      </div>
      {allIssues.length > 0 && (
        <div className="issues-grid">
          {allIssues.map((issue, i) => (
            <div key={i} className={`issue-card issue-${issue.tone}`}>
              <span className="issue-dot" />
              <span>{issue.text}</span>
            </div>
          ))}
        </div>
      )}
      {explainedIssues.length > 0 && (
        <div className="issues-grid">
          {explainedIssues.map((issue, i) => (
            <div key={i} className={`issue-card issue-${riskBadgeTone(issue.severity)}`}>
              <span className="issue-dot" />
              <span className="issue-copy">
                <strong className="issue-title">{issue.title}</strong>
                {issue.affected_sections?.length > 0 && (
                  <div className="muted small">Affected: {issue.affected_sections.join(", ")}</div>
                )}
                <div className="muted small">{issue.reason}</div>
                {issue.next_action && (
                  <div className="muted small" style={{ marginTop: 4 }}>
                    <span className="action-label">Next:</span> {issue.next_action}
                  </div>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
      {recommendedFixOrder.length > 0 && (
        <>
          <h3 className="subhead fix-order-title">Recommended order</h3>
          <ol className="fix-order-list">
            {recommendedFixOrder.slice(0, 3).map((fix) => (
              <li key={fix.priority}>
                <span className="fix-number">{fix.priority}</span>
                <span><strong>{fix.section || fix.issue_type}</strong>{" "}{fix.fix}
                {fix.why && <div className="muted small">{fix.why}</div>}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function HighlightsPanel({ topWeakSections = [], topWeakSectionsExplained = [], topWeakAlignmentPairs = [], alignmentWeaknessesExplained = [] }) {
  if (!topWeakSections.length && !topWeakSectionsExplained.length && !topWeakAlignmentPairs.length && !alignmentWeaknessesExplained.length) return null;
  return (
    <section className="panel focus-panel">
      <div className="panel-heading-row">
        <div>
          <span className="section-eyebrow">Where to focus</span>
          <h2 className="panel-title">Weakest areas</h2>
        </div>
      </div>
      <div className="grid-2">
        <div>
          <h3 className="subhead">Top Weak Sections</h3>
          {topWeakSectionsExplained.length ? (
            <ul className="bare-list">
              {topWeakSectionsExplained.map((s, i) => (
                <li key={i}>
                  <strong>{s.section}</strong>{" "}
                  <Badge value={s.risk_level} tone={riskBadgeTone(s.risk_level)} />
                  <div className="muted small">{s.reason}</div>
                  {s.weak_criteria?.length > 0 && (
                    <div className="muted small">Weak: {s.weak_criteria.join(", ")}</div>
                  )}
                  {s.next_action && (
                    <div className="muted small">Fix: {s.next_action}</div>
                  )}
                </li>
              ))}
            </ul>
          ) : topWeakSections.length ? (
            <ul className="bare-list">
              {topWeakSections.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None</p>
          )}
        </div>
        <div>
          <h3 className="subhead">Top Weak Alignment Pairs</h3>
          {alignmentWeaknessesExplained.length ? (
            <ul className="bare-list">
              {alignmentWeaknessesExplained.map((p, i) => (
                <li key={i}>
                  <strong>{p.section_pair}</strong>{" "}
                  <Badge value={p.risk} tone={riskBadgeTone(p.risk)} />
                  <div className="muted small">{p.reason}</div>
                  {p.next_action && (
                    <div className="muted small">Fix: {p.next_action}</div>
                  )}
                </li>
              ))}
            </ul>
          ) : topWeakAlignmentPairs.length ? (
            <ul className="bare-list">
              {topWeakAlignmentPairs.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None</p>
          )}
        </div>
      </div>
    </section>
  );
}

const MAJOR_STATUS_TONES = {
  "Detected Major Heading": "ok",
  "Detected Chapter Marker": "ok",
  "Merged Split Heading": "ok",
  "Derived Subsection from Introduction": "warn",
  "Fallback Extracted from Introduction": "warn",
  "Fallback Extracted": "warn",
  "Ignored Caption": "warn",
  "Ignored Front Matter": "warn",
  "Ignored Minor Heading": "warn",
  "Ignored Table of Contents Entry": "warn",
  Unknown: "muted"
};

function statusTone(status) {
  return MAJOR_STATUS_TONES[status] || "muted";
}

function resolvedSectionLabel(section) {
  if (!section) return "Unknown / Mixed Section";
  return section.resolved_section_label
    || section["Resolved Section Label"]
    || section.display_section
    || section["Display Section"]
    || section.predicted_section
    || section["Predicted Section"]
    || section.scoring_section
    || section["Scoring Section"]
    || section.section_name
    || section["Section Name"]
    || "Unknown / Mixed Section";
}

function DetectedHeadingsPanel({ majorHeadings = [] }) {

  return (
    <section className="panel">
      <h2 className="panel-title">
        Detected Major Headings ({majorHeadings.length})
      </h2>
      {majorHeadings.length === 0 ? (
        <p className="muted">
          No major thesis section headings were detected. Ensure the
          manuscript has clear major headings such as ABSTRACT, INTRODUCTION,
          METHODOLOGY, RESULTS AND DISCUSSION, or CHAPTER 1-5.
        </p>
      ) : (
        <HeadingsTable rows={majorHeadings} />
      )}
    </section>
  );
}

function HeadingsTable({ rows }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Line</th>
            <th>Raw Heading</th>
            <th>Normalized Section</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h, i) => {
            const status = h.status
              || (h.is_chapter_marker
                ? "Detected Chapter Marker"
                : h.normalized && h.normalized !== "Unknown"
                ? "Detected Major Heading"
                : "Unknown");
            return (
              <tr key={`${h.line_number}-${i}`}>
                <td>{h.line_number || "-"}</td>
                <td>{h.raw_heading || h.raw}</td>
                <td>{h.normalized_section || h.normalized}</td>
                <td>
                  <Badge value={status} tone={statusTone(status)} />
                  {h.explanation && (
                    <div className="muted small" style={{ marginTop: 4 }}>
                      {h.explanation}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SectionSummaryPanel({ sectionResults = [] }) {
  if (!sectionResults.length) return null;
  return (
    <section className="panel section-summary-panel">
      <div className="panel-heading-row">
        <div>
          <span className="section-eyebrow">Chapter overview</span>
          <h2 className="panel-title">Section readiness</h2>
        </div>
        <span className="count-chip">{sectionResults.length} sections</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Section</th>
              <th>Scoring Section</th>
              <th>Predicted</th>
              <th>Words</th>
              <th>Score</th>
              <th>Risk</th>
              <th>Weak Ev.</th>
              <th>Top Weak Areas</th>
            </tr>
          </thead>
          <tbody>
            {sectionResults.map((s, i) => (
              <tr key={i}>
                <td>{resolvedSectionLabel(s)}</td>
                <td>{s["Scoring Section"]}</td>
                <td className="muted small">
                  {resolvedSectionLabel(s)}
                  {s["Semantic Predicted Section"] && s["Semantic Predicted Section"] !== resolvedSectionLabel(s) && (
                    <div>Semantic: {s["Semantic Predicted Section"]}</div>
                  )}
                </td>
                <td>{s["Word Count"]}</td>
                <td>
                  <strong>{s["Defense Score"]}</strong>
                  <span className="muted small">/100</span>
                </td>
                <td>
                  <Badge value={s["Risk Level"]} tone={riskBadgeTone(s["Risk Level"])} />
                </td>
                <td>{s["Weak Evidence Count"]}</td>
                <td className="muted small">{s["Top Weak Areas"]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AlignmentMatrixPanel({ rows = [] }) {
  if (!rows.length) return null;
  const chartData = rows
    .filter((r) => r["Similarity Score"] !== null && r["Similarity Score"] !== undefined)
    .map((r) => ({
      name: shortenPair(r["Section Pair"]),
      score: Number(r["Similarity Score"]),
      level: r["Alignment Level"]
    }));

  return (
    <section className="panel">
      <h2 className="panel-title">Alignment Matrix</h2>
      {chartData.length > 0 ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--chart-axis)" tick={{ fontSize: 11 }} interval={0} />
              <YAxis domain={[0, 1]} stroke="var(--chart-axis)" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={{ fill: "var(--chart-hover)" }} />
              <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={coverageFill(entry.level.replace(" Alignment", ""))} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="muted">No similarity scores available — sections may be missing.</p>
      )}

      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Section Pair</th>
              <th>Similarity</th>
              <th>Alignment</th>
              <th>Risk</th>
              <th>Interpretation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r["Section Pair"]}</td>
                <td>
                  {r["Similarity Score"] == null ? (
                    <Badge value="Missing Section" tone="danger" />
                  ) : (
                    Number(r["Similarity Score"]).toFixed(3)
                  )}
                </td>
                <td>
                  <Badge value={r["Alignment Level"]} tone={alignmentBadgeTone(r["Alignment Level"])} />
                </td>
                <td>
                  <Badge value={r["Risk"]} tone={riskBadgeTone(r["Risk"])} />
                </td>
                <td className="muted small">{r["Interpretation"]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EvidenceSimpleSummary({ summary }) {
  const groups = [
    {
      title: "Critical Missing Evidence",
      rows: summary.critical_missing_evidence || []
    },
    {
      title: "Weakest Evidence",
      rows: summary.top_weak_evidence || []
    },
    {
      title: "Strongest Evidence",
      rows: summary.strongest_evidence || []
    }
  ];

  if (!groups.some((group) => group.rows.length)) return null;

  return (
    <div className="grid-3" style={{ marginBottom: 12 }}>
      {groups.map((group) => (
        <div key={group.title}>
          <h3 className="subhead">{group.title}</h3>
          {group.rows.length ? (
            <ul className="bare-list">
              {group.rows.slice(0, 5).map((row, i) => (
                <li key={i}>
                  <Badge value={row.coverage_level || row["Coverage Level"]} tone={coverageBadgeTone(row.coverage_level || row["Coverage Level"])} />{" "}
                  <strong>{row.section ? `${row.section}: ` : ""}{row.criterion || row["Evidence Area"]}</strong>
                  {row.display_score_label && <> ({row.display_score_label})</>}
                  {row.next_action && (
                    <div className="muted small" style={{ marginTop: 4 }}>
                      {row.next_action}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">None detected.</p>
          )}
        </div>
      ))}
    </div>
  );
}

function EvidenceCoveragePanel({ result, isManuscript, prevResult }) {
  const [selectedSectionName, setSelectedSectionName] = useState("Overall");

  useEffect(() => {
    setSelectedSectionName("Overall");
  }, [result.document_hash]);

  let rows = [];
  let detailedRows = [];
  let summary = result.evidence_summary_simple || null;
  let currentSectionCount = 0;

  if (isManuscript) {
    if (selectedSectionName === "Overall") {
      rows = result.evidence_display_rows || result.manuscript_evidence_summary || [];
      detailedRows = result.manuscript_evidence_summary || [];
      summary = result.evidence_summary_simple || summary;
      currentSectionCount = result.word_count || 0;
    } else {
      const sec = result.section_details?.find(s => resolvedSectionLabel(s) === selectedSectionName);
      rows = sec ? (sec.evidence_display_rows || sec.evidence_coverage) : [];
      detailedRows = sec ? sec.evidence_coverage : [];
      summary = sec ? sec.evidence_summary_simple : summary;
      currentSectionCount = sec ? sec.word_count : 0;
    }
  } else {
    rows = result.evidence_display_rows || result.evidence_coverage || [];
    detailedRows = result.evidence_coverage || [];
    summary = result.evidence_summary_simple || summary;
    currentSectionCount = result.word_count || 0;
  }

  if (!rows) rows = [];
  if (!detailedRows) detailedRows = [];

  const chartData = rows.map((r) => ({
    name: r["Evidence Area"] || r.criterion,
    score: evidenceChartScore(r),
    level: r["Coverage Level"] || r.coverage_level
  }));
  const chartHeight = Math.max(220, chartData.length * 32 + 60);
  const avgSimilarity = chartData.length > 0 ? chartData.reduce((acc, curr) => acc + curr.score, 0) / chartData.length : 0;

  let warningMsg = null;
  if (prevResult && result) {
      if (prevResult.document_hash === result.document_hash && prevResult.source_filename !== result.source_filename) {
         warningMsg = "Uploaded text did not change. Please check document extraction.";
      } else if (prevResult.document_hash !== result.document_hash) {
          let prevRows = isManuscript ? prevResult.evidence_display_rows || prevResult.manuscript_evidence_summary : prevResult.evidence_display_rows || prevResult.evidence_coverage;
          if (prevRows && rows && prevRows.length === rows.length) {
              const same = rows.every((r, i) => {
                  const p = prevRows[i];
                  return (r["Evidence Area"] || r.criterion) === (p["Evidence Area"] || p.criterion) &&
                         (r["Similarity Score"] ?? r.similarity_score) === (p["Similarity Score"] ?? p.similarity_score);
              });
              if (same && rows.length > 0) {
                  warningMsg = "Evidence coverage did not change. Possible stale result or extraction issue.";
              }
          }
      }
  }

  const sectionOptions = isManuscript && result.section_details ? ["Overall", ...result.section_details.map(s => resolvedSectionLabel(s))] : [];

  return (
    <section className="panel">
      <h2 className="panel-title">Evidence Coverage</h2>
      
      {isManuscript && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ marginRight: 8, fontWeight: 500 }}>Select section:</label>
            <select id="evidence-section" name="evidence_section" className="section-select" value={selectedSectionName} onChange={(e) => setSelectedSectionName(e.target.value)}>
              {sectionOptions.map(opt => <option key={opt} value={opt}>{opt === "Overall" ? "Overall (Average)" : opt}</option>)}
            </select>
          </div>
      )}

      {warningMsg && <div className="alert alert-warn" style={{ marginBottom: 12 }}>{warningMsg}</div>}

      {summary && (
        <EvidenceSimpleSummary summary={summary} />
      )}

      <h3 className="subhead">Priority Evidence Display</h3>
      <div className="badge-row" style={{ marginBottom: 12 }}>
        {rows.map((r, i) => (
          <Badge key={i} value={r["Evidence Area"] || r.criterion} tone="muted" />
        ))}
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            key={`${result.document_hash}-${selectedSectionName}`}
            data={chartData}
            layout="vertical"
            margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          >
            <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
            <XAxis type="number" domain={[0, 1]} stroke="var(--chart-axis)" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              stroke="var(--chart-axis)"
              width={180}
              tick={{ fontSize: 11 }}
            />
            <Tooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={{ fill: "var(--chart-hover)" }} />
            <Bar dataKey="score" radius={[0, 6, 6, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={coverageFill(entry.level)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="technical-meta">
        <summary>Analysis details</summary>
        <dl>
          <div><dt>Document ID</dt><dd>{result.document_hash ? result.document_hash.substring(0, 8) : "N/A"}</dd></div>
          <div><dt>Source</dt><dd>{result.source_filename || "Pasted text"}</dd></div>
          <div><dt>Selected section</dt><dd>{selectedSectionName === "Overall" ? (isManuscript ? "Overall average" : resolvedSectionLabel(result)) : selectedSectionName}</dd></div>
          <div><dt>Scoring section</dt><dd>{isManuscript && selectedSectionName !== "Overall" ? result.section_details?.find(s => resolvedSectionLabel(s) === selectedSectionName)?.scoring_section : result.scoring_section || "Overall"}</dd></div>
          <div><dt>Word count</dt><dd>{currentSectionCount}</dd></div>
          <div><dt>Criteria</dt><dd>{chartData.length}</dd></div>
          <div><dt>Average similarity</dt><dd>{avgSimilarity.toFixed(3)}</dd></div>
        </dl>
      </details>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Evidence Area</th>
              <th>Display Coverage</th>
              <th>Coverage Level</th>
              <th>Next Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r["Evidence Area"] || r.criterion}</td>
                <td>{evidenceScoreLabel(r)}</td>
                <td>
                  <Badge value={r["Coverage Level"] || r.coverage_level} tone={coverageBadgeTone(r["Coverage Level"] || r.coverage_level)} />
                </td>
                <td className="muted small">{r.next_action || r.Interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detailedRows.length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary className="muted small">Show technical evidence details</summary>
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evidence Area</th>
                  <th>Raw Similarity</th>
                  <th>Coverage Level</th>
                  <th>Interpretation</th>
                </tr>
              </thead>
              <tbody>
                {detailedRows.map((r, i) => (
                  <tr key={i}>
                    <td>{r["Evidence Area"] || r.criterion}</td>
                    <td>{Number(r["Similarity Score"] ?? r.similarity_score ?? 0).toFixed(3)}</td>
                    <td>
                      <Badge value={r["Coverage Level"] || r.coverage_level} tone={coverageBadgeTone(r["Coverage Level"] || r.coverage_level)} />
                    </td>
                    <td className="muted small">{r.Interpretation || r.interpretation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}

function SectionDetailsPanel({ sections = [] }) {
  if (!sections.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Section Details</h2>
      <p className="muted small" style={{ margin: "0 0 12px" }}>
        Click a section to expand its diagnosis, recommendations, and technical details.
      </p>
      <div className="detail-cards">
        {sections.map((section, i) => (
          <SectionDetailCard key={i} section={section} />
        ))}
      </div>
    </section>
  );
}

function SectionDetailCard({ section }) {
  const priorityFixes = (section.priority_fixes || []).slice(0, 3);
  const evidenceCoverage = section.evidence_coverage || [];
  const deductions = section.deductions || [];

  const isGemini = section.feedback_mode === "Gemini-grounded";
  
  const diagnosis = isGemini && section.dynamic_diagnosis ? section.dynamic_diagnosis : section.plain_language_diagnosis;
  const nextBestAction = isGemini && section.dynamic_next_best_action ? section.dynamic_next_best_action : section.next_best_action;
  const panelRisk = isGemini && section.dynamic_panel_risk ? section.dynamic_panel_risk : section.panel_risk;
const suggestedWording = isGemini && section.dynamic_suggested_revision_wording ? section.dynamic_suggested_revision_wording : (section.suggested_revision_wording || []);
  const defenseQs = isGemini && section.dynamic_defense_questions ? section.dynamic_defense_questions : (section.defense_questions || []).slice(0, 3);
  const highlights = section.contextual_highlights || section.highlights || [];

  return (
    <details className="detail-card">
      <summary>
        <div className="detail-card-head">
          <span className="detail-section-name">
            {resolvedSectionLabel(section)}
          </span>
          <span className="detail-meta">
            <Badge value={section.risk_level} tone={riskBadgeTone(section.risk_level)} />
            <span className="muted small">
              {section.defense_score}/100 · {section.word_count} words
            </span>
          </span>
        </div>
      </summary>

      <div className="detail-body">
        {diagnosis && (
          <>
            <h4 className="micro-head">
              Diagnosis
            </h4>
            <p>{diagnosis}</p>
          </>
        )}

        {nextBestAction && (
          <>
            <h4 className="micro-head">
              Next Best Action
            </h4>
            <p className="next-action-copy">{nextBestAction}</p>
          </>
        )}

        {panelRisk && (
          <>
            <h4 className="micro-head">
              Likely Panel Risk
            </h4>
            <p>{panelRisk}</p>
          </>
        )}

        <h4 className="micro-head">Contextual Highlights</h4>
        {highlights.length > 0 ? (
          <div className="highlight-cards" style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
            {highlights.map((h, i) => {
              let borderCol = "#facc15"; // Yellow for Vague Evidence
              let bgCol = "rgba(250, 204, 21, 0.1)";
              if (h.highlight_type === "Overclaim Risk") {
                borderCol = "#f87171"; // Red
                bgCol = "rgba(248, 113, 113, 0.1)";
              } else if (h.highlight_type === "Needs Support") {
                borderCol = "#fb923c"; // Orange
                bgCol = "rgba(251, 146, 60, 0.1)";
              }
              return (
                <article key={i} className="context-highlight" style={{ "--highlight-color": borderCol, "--highlight-bg": bgCol }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                    <strong style={{ color: borderCol, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h.highlight_type}</strong>
                    <Badge value={h.severity} tone={h.severity === "High" ? "danger" : "warn"} />
                  </div>
                  <blockquote>{h.text}</blockquote>
                  <p className="muted small"><strong>Why:</strong> {h.reason}</p>
                  <p className="highlight-suggestion"><strong>Try:</strong> {h.suggested_revision}</p>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="muted small" style={{ marginBottom: "16px" }}>No major overclaim or vague evidence highlights detected.</p>
        )}

        {priorityFixes.length > 0 && (
          <>
            <h4 className="micro-head">Top Recommendations</h4>
            <ul className="bare-list">
              {priorityFixes.map((fix, i) => (
                <li key={i}>
                  <Badge
                    value={fix.Priority || "Med"}
                    tone={fix.Priority === "High" ? "danger" : "warn"}
                  />{" "}
                  <strong>{fix.Issue}</strong>
                  {fix["Suggested Fix"] && <> — {fix["Suggested Fix"]}</>}
                </li>
              ))}
            </ul>
          </>
        )}

        {suggestedWording.length > 0 && (
          <>
            <h4 className="micro-head">
              Suggested Revision Wording
            </h4>
            <ul className="bare-list">
              {suggestedWording.map((wording, i) => (
                <li key={i} className="wording-card">
                  {wording}
                </li>
              ))}
            </ul>
          </>
        )}

        {defenseQs.length > 0 && (
          <>
            <h4 className="micro-head">
              Top 3 Defense Questions
            </h4>
            <ul className="bare-list">
              {defenseQs.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </>
        )}

        <details className="nested-expander">
          <summary>Technical Details (evidence coverage, score breakdown &amp; deductions)</summary>
          {section.score_breakdown && (
            <>
              <h4 className="micro-head">Score Breakdown</h4>
              <div className="exec-grid" style={{ marginBottom: 12 }}>
                {Object.entries(section.score_breakdown).map(([k, v]) => (
                  <ScoreCard key={k} label={k.replace(/_/g, " ")} value={typeof v === "number" ? v.toFixed(2) : v} />
                ))}
              </div>
            </>
          )}
          {section.criteria_used?.length > 0 && (
            <>
              <h4 className="micro-head">Criteria Used for This Section</h4>
              <div className="badge-row">
                {section.criteria_used.map((criterion, i) => (
                  <Badge key={i} value={criterion} tone="muted" />
                ))}
              </div>
            </>
          )}
          {evidenceCoverage.length > 0 && (
            <>
              <h4 className="micro-head">Evidence Coverage</h4>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Evidence Area</th>
                      <th>Similarity</th>
                      <th>Level</th>
                      <th>Interpretation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidenceCoverage.map((e, i) => (
                      <tr key={i}>
                        <td>{e["Evidence Area"] || e.criterion}</td>
                        <td>{Number(e["Similarity Score"] ?? e.similarity_score ?? 0).toFixed(3)}</td>
                        <td>
                          <Badge
                            value={e["Coverage Level"] || e.coverage_level}
                            tone={coverageBadgeTone(e["Coverage Level"] || e.coverage_level)}
                          />
                        </td>
                        <td className="muted small">{e["Interpretation"] || e.interpretation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {deductions.length > 0 && (
            <>
              <h4 className="micro-head">Deductions</h4>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Evidence Area</th>
                      <th>Deduction</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deductions.map((d, i) => (
                      <tr key={i}>
                        <td>{d["Evidence Area"]}</td>
                        <td>-{d.Deduction}</td>
                        <td className="muted small">{d.Reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </details>
      </div>
    </details>
  );
}

function OverallNotesPanel({ notes = [] }) {
  if (!notes.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Defense Preparation Notes</h2>
      <ul className="bare-list">
        {notes.map((note, i) => (
          <li key={i}>{note}</li>
        ))}
      </ul>
    </section>
  );
}

function DownloadReportPanel({ filename }) {
  if (!filename) return null;
  return (
    <section className="panel report-cta">
      <div>
        <span className="section-eyebrow">Take it with you</span>
        <h2 className="panel-title">Download the review report</h2>
        <p className="muted small">A printable copy of the scores, evidence gaps, and revision priorities.</p>
      </div>
      <a
        className="btn-primary download-link"
        href={`${API_BASE_URL}/download-report/${filename}`}
        target="_blank"
        rel="noreferrer"
      >
        Download PDF
      </a>
    </section>
  );
}

/* ───────────────────────── Section Result Panel ───────────────────────── */

function ContextualHighlightsPanel({ highlights = [] }) {
  if (!highlights.length) return null;
  return (
    <section className="panel highlights-panel">
      <div className="panel-heading-row">
        <div>
          <span className="section-eyebrow">Check these claims</span>
          <h2 className="panel-title">Contextual highlights</h2>
        </div>
        <span className="count-chip">{highlights.length}</span>
      </div>
        <div className="context-highlight-list">
          {highlights.map((h, i) => {
            let borderCol = "#facc15";
            let bgCol = "rgba(250,204,21,0.1)";
            if (h.highlight_type === "Overclaim Risk") {
              borderCol = "#f87171";
              bgCol = "rgba(248,113,113,0.1)";
            } else if (h.highlight_type === "Needs Support") {
              borderCol = "#fb923c";
              bgCol = "rgba(251,146,60,0.1)";
            }
            return (
              <article key={i} className="context-highlight" style={{ "--highlight-color": borderCol, "--highlight-bg": bgCol }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                  <strong style={{ color: borderCol, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h.highlight_type}</strong>
                  <Badge value={h.severity} tone={h.severity === "High" ? "danger" : "warn"} />
                </div>
                <blockquote>{h.text}</blockquote>
                <p className="muted small"><strong>Why:</strong> {h.reason}</p>
                <p className="highlight-suggestion"><strong>Try:</strong> {h.suggested_revision}</p>
              </article>
            );
          })}
        </div>
    </section>
  );
}

function SectionResultPanel({ result, prevResult }) {
  const isGemini = result.feedback_mode === "Gemini-grounded";
  const diagnosis = isGemini && result.dynamic_diagnosis ? result.dynamic_diagnosis : result.plain_language_diagnosis;
  const nextBestAction = isGemini && result.dynamic_next_best_action ? result.dynamic_next_best_action : result.next_best_action;
  const panelRisk = isGemini ? result.dynamic_panel_risk : result.panel_risk;
  const highlights = result.contextual_highlights || [];
  const suggestedWording = isGemini && result.dynamic_suggested_revision_wording
    ? result.dynamic_suggested_revision_wording
    : result.suggested_revision_wording || [];

  return (
    <div className="results-dashboard">
      <ResultHeading
        title="Section review"
        subtitle="Your score, strongest next move, and supporting evidence are organized below."
        result={result}
      />
      <ExecutiveSummary result={result} />
      <section className="review-brief" aria-label="Review brief">
        {diagnosis && (
          <article className="brief-card brief-diagnosis">
            <span className="brief-index">01</span>
            <div>
              <span className="section-eyebrow">What we found</span>
              <h3>Diagnosis</h3>
              <p>{diagnosis}</p>
              {result.score_summary && <p className="muted small">{result.score_summary}</p>}
            </div>
          </article>
        )}
        {nextBestAction && (
          <article className="brief-card brief-action">
            <span className="brief-index">02</span>
            <div>
              <span className="section-eyebrow">Do this first</span>
              <h3>Next best action</h3>
              <p>{nextBestAction}</p>
            </div>
          </article>
        )}
        {panelRisk && (
          <article className="brief-card brief-risk">
            <span className="brief-index">03</span>
            <div>
              <span className="section-eyebrow">Prepare to answer</span>
              <h3>Likely panel concern</h3>
              <p>{panelRisk}</p>
            </div>
          </article>
        )}
      </section>
      <ContextualHighlightsPanel highlights={highlights} isGemini={isGemini} />
      <EvidenceCoveragePanel result={result} isManuscript={false} prevResult={prevResult} />
      <RecommendationsPanel
        priorityFixes={result.priority_fixes}
        revisions={isGemini ? [] : result.revision_suggestions}
        suggestedWording={suggestedWording}
        defenseQs={isGemini && result.dynamic_defense_questions ? result.dynamic_defense_questions : result.defense_questions}
        isGemini={isGemini}
      />
      <DownloadReportPanel filename={result.report_filename} />
    </div>
  );
}

function RecommendationsPanel({ priorityFixes = [], revisions = [], suggestedWording = [], defenseQs = [], isGemini = false }) {
  if (!priorityFixes.length && !revisions.length && !suggestedWording.length && !defenseQs.length) return null;
  return (
    <section className="panel recommendations-panel">
      <div className="panel-heading-row">
        <div>
          <span className="section-eyebrow">Revision plan</span>
          <h2 className="panel-title">Recommendations &amp; defense prep</h2>
        </div>
      </div>
      <div className="recommendation-grid">

      {priorityFixes.length > 0 && (
        <div className="recommendation-block">
          <h3 className="subhead">Priority fixes</h3>
          <ul className="bare-list">
            {priorityFixes.slice(0, 5).map((fix, i) => (
              <li key={i}>
                <Badge
                  value={fix.Priority || "Med"}
                  tone={fix.Priority === "High" ? "danger" : "warn"}
                />{" "}
                <strong>{fix.Issue}</strong>
                {fix["Suggested Fix"] && <> — {fix["Suggested Fix"]}</>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {revisions.length > 0 && (
        <div className="recommendation-block">
          <h3 className="subhead">
            Revision Suggestions
          </h3>
          <ul className="bare-list">
            {revisions.slice(0, 5).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {suggestedWording.length > 0 && (
        <div className="recommendation-block recommendation-wording">
          <h3 className="subhead">
            Suggested Revision Wording
          </h3>
          <ul className="bare-list">
            {suggestedWording.slice(0, 3).map((w, i) => (
              <li key={i} className="wording-card">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {defenseQs.length > 0 && (
        <div className="recommendation-block">
          <h3 className="subhead">
            Likely Defense Questions
          </h3>
          <ol className="question-list">
            {defenseQs.slice(0, 5).map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
      </div>
    </section>
  );
}

/* ───────────────────────── Compare Result Panel ───────────────────────── */

function scoreChangeTone(v) {
  if (v > 0) return "ok";
  if (v < 0) return "danger";
  return "muted";
}

function CompareResultPanel({ result }) {
  const comp = result.comparison || {};
  const scoreImprovement = comp.score_improvement;
  const semImprovement = comp.semantic_improvement_score ?? comp.semantic_improvement;
  const evidenceComparison = comp.evidence_comparison_table || comp.evidence_comparison || [];
  const improvedAreas = comp.improved_evidence_areas || comp.improved_areas || [];
  const resolvedAreas = comp.resolved_weak_areas || comp.resolved_areas || [];
  const remainingWeak = comp.remaining_weak_areas || [];

  const semLabel = semImprovement != null
    ? `${semImprovement >= 0 ? "+" : ""}${(semImprovement * 100).toFixed(1)}%`
    : "-";
  const semTone = semImprovement > 0.02 ? "ok" : semImprovement > 0 ? "warn" : "muted";

  return (
    <>
      <section className="panel">
        <h2 className="panel-title">Revision Comparison</h2>
        <div className="exec-grid">
          <ScoreCard
            label="Original Score"
            value={comp.original_score != null ? `${comp.original_score}/100` : "-"}
            tone={riskBadgeTone(comp.original_risk)}
          />
          <ScoreCard
            label="Revised Score"
            value={comp.revised_score != null ? `${comp.revised_score}/100` : "-"}
            tone={riskBadgeTone(comp.revised_risk)}
          />
          <ScoreCard
            label="Risk Change"
            value={`${comp.original_risk || "?"} → ${comp.revised_risk || "?"}`}
          />
          <ScoreCard
            label="Final Score Change"
            value={scoreImprovement != null
              ? `${scoreImprovement > 0 ? "+" : ""}${scoreImprovement}`
              : "-"}
            tone={scoreChangeTone(scoreImprovement)}
          />
          <ScoreCard
            label="Semantic Improvement"
            value={semLabel}
            tone={semTone}
          />
          <ScoreCard
            label="Avg Original Similarity"
            value={comp.avg_original_similarity != null
              ? comp.avg_original_similarity.toFixed(3)
              : "-"}
          />
          <ScoreCard
            label="Avg Revised Similarity"
            value={comp.avg_revised_similarity != null
              ? comp.avg_revised_similarity.toFixed(3)
              : "-"}
          />
        </div>
        {comp.summary && (
          <div className={`alert alert-${semImprovement > 0 || scoreImprovement > 0 ? "info" : "warn"}`}
               style={{ marginTop: 12 }}>
            {comp.summary}
          </div>
        )}
      </section>

      <section className="panel">
        <h2 className="panel-title">Evidence Area Changes</h2>
        <div className="grid-2">
          <div>
            <h3 className="subhead">Improved Areas (Δ ≥ 0.05)</h3>
            {improvedAreas.length ? (
              <ul className="bare-list">
                {improvedAreas.map((a, i) => (
                  <li key={i}><Badge value={a} tone="ok" /></li>
                ))}
              </ul>
            ) : (
              <p className="muted">No areas improved by ≥ 0.05.</p>
            )}
          </div>
          <div>
            <h3 className="subhead">Newly Supported (Weak → Moderate/Strong)</h3>
            {resolvedAreas.length ? (
              <ul className="bare-list">
                {resolvedAreas.map((a, i) => (
                  <li key={i}><Badge value={a} tone="ok" /></li>
                ))}
              </ul>
            ) : (
              <p className="muted">No areas crossed the coverage threshold.</p>
            )}
          </div>
          <div>
            <h3 className="subhead">Unchanged Weak Areas</h3>
            {remainingWeak.length ? (
              <ul className="bare-list">
                {remainingWeak.map((a, i) => (
                  <li key={i}><Badge value={a} tone="danger" /></li>
                ))}
              </ul>
            ) : (
              <p className="muted">None — all expected areas improved.</p>
            )}
          </div>
        </div>
      </section>

      {evidenceComparison.length > 0 && (
        <section className="panel">
          <h2 className="panel-title">Evidence Comparison Table</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evidence Area</th>
                  <th>Orig. Score</th>
                  <th>Rev. Score</th>
                  <th>Change</th>
                  <th>Orig. Level</th>
                  <th>Rev. Level</th>
                </tr>
              </thead>
              <tbody>
                {evidenceComparison.map((row, i) => (
                  <tr key={i}
                    style={row.improved
                      ? { background: "rgba(74,222,128,0.04)" }
                      : undefined}
                  >
                    <td>
                      {row.evidence_area}
                      {row.is_expected && (
                        <span className="muted small"> ★</span>
                      )}
                    </td>
                    <td>{row.original_score?.toFixed(3)}</td>
                    <td>{row.revised_score?.toFixed(3)}</td>
                    <td>
                      <span style={{
                        color: row.score_change > 0.001
                          ? "#2f7d4c"
                          : row.score_change < -0.001
                          ? "#c53d3d"
                          : "#66736e"
                      }}>
                        {row.score_change > 0 ? "+" : ""}
                        {row.score_change?.toFixed(3)}
                      </span>
                    </td>
                    <td>
                      <Badge
                        value={row.original_level}
                        tone={coverageBadgeTone(row.original_level)}
                      />
                    </td>
                    <td>
                      <Badge
                        value={row.revised_level}
                        tone={coverageBadgeTone(row.revised_level)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginTop: 6 }}>
            ★ Expected area for this section type. Highlighted rows improved by ≥ 0.05.
          </p>
        </section>
      )}
    </>
  );
}

/* ───────────────────────── Evaluate Result Panel ───────────────────────── */

function computeSectionAccuracy(rows) {
  const groups = {};
  for (const row of rows || []) {
    const section = row.true_section || "Unknown";
    if (!groups[section]) groups[section] = { samples: 0, correct: 0 };
    groups[section].samples += 1;
    if (row.section_correct) groups[section].correct += 1;
  }
  return Object.entries(groups)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([section, { samples, correct }]) => ({
      section,
      samples,
      correct,
      accuracy: samples > 0 ? ((correct / samples) * 100).toFixed(1) : "0.0"
    }));
}

function accuracyTone(pct) {
  const n = parseFloat(pct);
  if (n >= 80) return "ok";
  if (n >= 60) return "warn";
  return "danger";
}

function EvaluateResultPanel({ result }) {
  const summary = result.summary || {};
  const perSection = computeSectionAccuracy(result.results);
  const totalSamples = summary.total_samples ?? 0;
  const totalCorrect = summary.correct_classifications ?? 0;
  const overallAccuracy = totalSamples > 0
    ? ((totalCorrect / totalSamples) * 100).toFixed(1)
    : "-";

  return (
    <>
      <section className="panel">
        <h2 className="panel-title">Evaluation Summary</h2>
        <div className="exec-grid">
          <ScoreCard
            label="Classification Accuracy"
            value={`${summary.section_classification_accuracy ?? "-"}%`}
          />
          <ScoreCard
            label="Total Samples"
            value={totalSamples}
          />
          <ScoreCard
            label="Correct Classifications"
            value={totalCorrect}
          />
          <ScoreCard
            label="Avg Score Diff"
            value={summary.average_absolute_score_difference ?? "-"}
          />
          <ScoreCard
            label="Issue Agreement"
            value={`${summary.issue_detection_agreement ?? "-"}%`}
          />
          <ScoreCard
            label="Avg Processing Time"
            value={`${summary.average_processing_time ?? "-"}s`}
          />
        </div>
      </section>

      {perSection.length > 0 && (
        <section className="panel">
          <h2 className="panel-title">Per-Section Classification Accuracy</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Section Type</th>
                  <th>Samples</th>
                  <th>Correct</th>
                  <th>Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {perSection.map((row, i) => (
                  <tr key={i}>
                    <td>{row.section}</td>
                    <td>{row.samples}</td>
                    <td>{row.correct}</td>
                    <td>
                      <Badge value={`${row.accuracy}%`} tone={accuracyTone(row.accuracy)} />
                    </td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 600, borderTop: "2px solid #c7d5d0" }}>
                  <td>Overall</td>
                  <td>{totalSamples}</td>
                  <td>{totalCorrect}</td>
                  <td>
                    <Badge value={`${overallAccuracy}%`} tone={accuracyTone(overallAccuracy)} />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result.results_filename && (
        <section className="panel">
          <h2 className="panel-title">Download Results</h2>
          <a
            className="btn-primary download-link"
            href={`${API_BASE_URL}/download-report/${result.results_filename}`}
            target="_blank"
            rel="noreferrer"
          >
            Download Evaluation CSV
          </a>
        </section>
      )}
    </>
  );
}
