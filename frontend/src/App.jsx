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

const API_BASE_URL = "http://127.0.0.1:8000";

const TABS = [
  { id: "section", label: "Analyze Section" },
  { id: "manuscript", label: "Analyze Full Manuscript" },
  { id: "compare", label: "Compare Revisions" },
  { id: "evaluate", label: "Evaluate Dataset" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState("section");
  const [backendStatus, setBackendStatus] = useState("checking");

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

  useEffect(() => {
    let cancelled = false;
    async function checkHealth() {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (!cancelled) setBackendStatus(res.ok ? "online" : "offline");
      } catch {
        if (!cancelled) setBackendStatus("offline");
      }
    }
    checkHealth();
    const id = setInterval(checkHealth, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  function clearOutput() {
    if (result) {
      prevResultRef.current = result;
    }
    setResult(null);
    setError("");
  }

  async function callJson(path, body) {
    setLoading(true);
    clearOutput();
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
      setResult(data);
    } catch (err) {
      setError(err.message || "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function callForm(path, formData) {
    setLoading(true);
    clearOutput();
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        body: formData
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
      setResult(data);
    } catch (err) {
      setError(err.message || "Request failed.");
    } finally {
      setLoading(false);
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
        <div className="brand">
          <span className="brand-tag">SAGE-Review</span>
          <h1>Intelligent Thesis Defense Readiness &amp; Manuscript Evaluation</h1>
          <p className="muted">
            AI/NLP semantic analysis for thesis section classification, evidence
            coverage, defense readiness scoring, and revision review.
          </p>
        </div>
        <div className={`status status-${backendStatus}`}>
          <span className="status-dot" />
          {backendStatus === "online" && "Backend Online"}
          {backendStatus === "offline" && "Backend Offline"}
          {backendStatus === "checking" && "Checking Backend..."}
        </div>
      </header>

      <nav className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab ${activeTab === tab.id ? "tab-active" : ""}`}
            onClick={() => handleTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <section className="panel">
        {activeTab === "section" && (
          <Form title="Analyze a Single Thesis Section">
            <Field label="Thesis section text">
              <textarea
                rows={12}
                value={sectionText}
                onChange={(e) => updateSectionText(e.target.value)}
                placeholder="Paste an Introduction, Methodology, Results, or Conclusion section..."
              />
            </Field>
            <Field label="Or upload a document (PDF / DOCX / TXT)">
              <input
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
          <Form title="Analyze a Full Manuscript">
            <Field label="Full manuscript text">
              <textarea
                rows={16}
                value={manuscriptText}
                onChange={(e) => updateManuscriptText(e.target.value)}
                placeholder="Paste the full thesis manuscript here..."
              />
            </Field>
            <Field label="Or upload a manuscript (PDF / DOCX / TXT)">
              <input
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
          <Form title="Compare Original and Revised Section">
            <div className="grid-2">
              <Field label="Original">
                <textarea
                  rows={12}
                  value={originalText}
                  onChange={(e) => updateOriginalText(e.target.value)}
                  placeholder="Paste the original section..."
                />
              </Field>
              <Field label="Revised">
                <textarea
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
          <Form title="Evaluate a Labeled Dataset (CSV)">
            <Field label="Evaluation CSV">
              <input
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

      {error && <div className="alert alert-error">{error}</div>}

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

function Form({ title, children }) {
  return (
    <div className="form">
      <h2 className="panel-title">{title}</h2>
      {children}
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
      {loading ? loadingLabel : label}
    </button>
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
  if (v === "complete") return "ok";
  if (v === "partial") return "warn";
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
  if (v === "strong") return "#4ade80";
  if (v === "moderate") return "#facc15";
  if (v === "weak") return "#f87171";
  return "#22d3ee";
}

function shortenPair(pair) {
  return String(pair || "")
    .replace(" <-> ", " ↔ ")
    .replace("Objectives of the Study", "Objectives")
    .replace("Results and Discussion", "Results");
}

const CHART_TOOLTIP_STYLE = {
  background: "#0f172a",
  border: "1px solid #1f2d4d",
  borderRadius: 6,
  color: "#e2e8f0",
  fontSize: 12
};

/* ───────────────────────── Manuscript Dashboard ───────────────────────── */

function ManuscriptDashboard({ result, prevResult }) {
  return (
    <>
      <ExecutiveSummary result={result} />
      <MainIssuesPanel issues={result.main_issues} extractionWarnings={result.extraction_warnings} />
      <HighlightsPanel
        topWeakSections={result.top_weak_sections}
        topWeakAlignmentPairs={result.top_weak_alignment_pairs}
      />
      <DetectedHeadingsPanel
        majorHeadings={result.major_detected_headings || result.detected_headings}
      />
      <SectionSummaryPanel sectionResults={result.section_results} />
      <AlignmentMatrixPanel
        rows={result.raw_alignment_results?.length ? result.raw_alignment_results : result.alignment_results}
      />
      <EvidenceCoveragePanel result={result} isManuscript={true} prevResult={prevResult} />
      <SectionDetailsPanel sections={result.section_details} />
      <OverallNotesPanel notes={result.overall_defense_notes} />
      <DownloadReportPanel filename={result.report_filename} />
    </>
  );
}

function ExecutiveSummary({ result }) {
  const score = result.overall_score ?? result.defense_score;
  const risk = result.overall_risk_level || result.risk_level;
  const confidence = result.analysis_confidence;
  const wordCount = result.word_count;
  const processingTime = result.processing_time_seconds;
  const isIncomplete = result.result_type === "Extraction Incomplete";

  const items = [
    score != null && {
      label: "Overall Readiness",
      value: isIncomplete ? "Not reliable" : `${score}/100`,
      tone: isIncomplete ? "muted" : riskBadgeTone(risk)
    },
    risk && {
      label: "Risk Level",
      value: <Badge value={risk} tone={riskBadgeTone(risk)} />
    },
    confidence && {
      label: "Analysis Confidence",
      value: <Badge value={confidence} tone={confidenceBadgeTone(confidence)} />
    },
    wordCount != null && {
      label: "Total Word Count",
      value: typeof wordCount === "number" ? wordCount.toLocaleString() : wordCount
    },
    processingTime != null && {
      label: "Processing Time",
      value: `${processingTime}s`
    }
  ].filter(Boolean);

  return (
    <section className="panel">
      <h2 className="panel-title">Executive Summary</h2>
      <div className="exec-grid">
        {items.map((item, i) => (
          <ScoreCard key={i} {...item} />
        ))}
      </div>
      {isIncomplete && result.recommendation && (
        <div className="alert alert-error" style={{ marginTop: 12 }}>
          <strong>{result.result_type}:</strong> {result.recommendation}
        </div>
      )}
    </section>
  );
}

function MainIssuesPanel({ issues = [], extractionWarnings = [] }) {
  const allIssues = [
    ...(extractionWarnings || []).map((w) => ({ text: w, tone: "warn" })),
    ...(issues || []).map((w) => ({ text: w, tone: "warn" }))
  ];
  if (!allIssues.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Main Issues</h2>
      <div className="issues-grid">
        {allIssues.map((issue, i) => (
          <div key={i} className={`issue-card issue-${issue.tone}`}>
            <span className="issue-dot" />
            <span>{issue.text}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function HighlightsPanel({ topWeakSections = [], topWeakAlignmentPairs = [] }) {
  if (!topWeakSections.length && !topWeakAlignmentPairs.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Highlights</h2>
      <div className="grid-2">
        <div>
          <h3 className="subhead">Top Weak Sections</h3>
          {topWeakSections.length ? (
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
          {topWeakAlignmentPairs.length ? (
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
    <section className="panel">
      <h2 className="panel-title">Section Summary</h2>
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
                <td>{s["Section Name"]}</td>
                <td>{s["Scoring Section"]}</td>
                <td className="muted small">{s["Predicted Section"]}</td>
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
              <CartesianGrid stroke="#1f2d4d" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} interval={0} />
              <YAxis domain={[0, 1]} stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={{ fill: "rgba(34,211,238,0.08)" }} />
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

function EvidenceCoveragePanel({ result, isManuscript, prevResult }) {
  const [selectedSectionName, setSelectedSectionName] = useState("Overall");

  let rows = [];
  let currentSectionCount = 0;

  if (isManuscript) {
    if (selectedSectionName === "Overall") {
      rows = result.manuscript_evidence_summary || [];
      currentSectionCount = result.word_count || 0;
    } else {
      const sec = result.section_details?.find(s => (s.section_name || s.predicted_section) === selectedSectionName);
      rows = sec ? sec.evidence_coverage : [];
      currentSectionCount = sec ? sec.word_count : 0;
    }
  } else {
    rows = result.evidence_coverage || [];
    currentSectionCount = result.word_count || 0;
  }

  if (!rows) rows = [];

  const chartData = rows.map((r) => ({
    name: r["Evidence Area"] || r.criterion,
    score: Number(r["Similarity Score"] || r.similarity_score) || 0,
    level: r["Coverage Level"] || r.coverage_level
  }));
  const chartHeight = Math.max(220, chartData.length * 32 + 60);
  const avgSimilarity = chartData.length > 0 ? chartData.reduce((acc, curr) => acc + curr.score, 0) / chartData.length : 0;

  let warningMsg = null;
  if (prevResult && result) {
      if (prevResult.document_hash === result.document_hash && prevResult.source_filename !== result.source_filename) {
         warningMsg = "Uploaded text did not change. Please check document extraction.";
      } else if (prevResult.document_hash !== result.document_hash) {
          let prevRows = isManuscript ? prevResult.manuscript_evidence_summary : prevResult.evidence_coverage;
          if (prevRows && rows && prevRows.length === rows.length) {
              const same = rows.every((r, i) => {
                  const p = prevRows[i];
                  return (r["Evidence Area"] || r.criterion) === (p["Evidence Area"] || p.criterion) &&
                         (r["Similarity Score"] || r.similarity_score) === (p["Similarity Score"] || p.similarity_score);
              });
              if (same && rows.length > 0) {
                  warningMsg = "Evidence coverage did not change. Possible stale result or extraction issue.";
              }
          }
      }
  }

  const sectionOptions = isManuscript && result.section_details ? ["Overall", ...result.section_details.map(s => s.section_name || s.predicted_section)] : [];

  return (
    <section className="panel">
      <h2 className="panel-title">Evidence Coverage</h2>
      
      {isManuscript && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ marginRight: 8, fontWeight: 500 }}>Select section:</label>
            <select value={selectedSectionName} onChange={(e) => setSelectedSectionName(e.target.value)} style={{ padding: "4px 8px", borderRadius: 4, background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155" }}>
              {sectionOptions.map(opt => <option key={opt} value={opt}>{opt === "Overall" ? "Overall (Average)" : opt}</option>)}
            </select>
          </div>
      )}

      {warningMsg && <div className="alert alert-warn" style={{ marginBottom: 12 }}>{warningMsg}</div>}

      <h3 className="subhead">Criteria used for this section</h3>
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
            <CartesianGrid stroke="#1f2d4d" horizontal={false} />
            <XAxis type="number" domain={[0, 1]} stroke="#94a3b8" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#94a3b8"
              width={180}
              tick={{ fontSize: 11 }}
            />
            <Tooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={{ fill: "rgba(34,211,238,0.08)" }} />
            <Bar dataKey="score" radius={[0, 6, 6, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={coverageFill(entry.level)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="muted small" style={{ marginTop: 12 }}>
        Showing evidence coverage for:<br/>
        - Document hash: {result.document_hash ? result.document_hash.substring(0, 8) : "N/A"}<br/>
        - File name: {result.source_filename || "Pasted Text"}<br/>
        - Selected section: {selectedSectionName === "Overall" ? (isManuscript ? "Overall (Average)" : result.section_name || result.predicted_section) : selectedSectionName}<br/>
        - Scoring section: {isManuscript && selectedSectionName !== "Overall" ? result.section_details?.find(s => (s.section_name || s.predicted_section) === selectedSectionName)?.scoring_section : result.scoring_section || "Overall"}<br/>
        - Section word count: {currentSectionCount}<br/>
        - Criteria count: {chartData.length}<br/>
        - Average similarity: {avgSimilarity.toFixed(3)}
      </div>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Evidence Area</th>
              <th>Similarity Score</th>
              <th>Coverage Level</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r["Evidence Area"] || r.criterion}</td>
                <td>{Number(r["Similarity Score"] || r.similarity_score).toFixed(3)}</td>
                <td>
                  <Badge value={r["Coverage Level"] || r.coverage_level} tone={coverageBadgeTone(r["Coverage Level"] || r.coverage_level)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
const suggestedWording = isGemini && section.dynamic_suggested_revision_wording ? section.dynamic_suggested_revision_wording : (section.suggested_revision_wording || []);
  const defenseQs = isGemini && section.dynamic_defense_questions ? section.dynamic_defense_questions : (section.defense_questions || []).slice(0, 3);
  const highlights = section.contextual_highlights || section.highlights || [];

  return (
    <details className="detail-card">
      <summary>
        <div className="detail-card-head">
          <span className="detail-section-name">
            {section.section_name || section.predicted_section}
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
              Diagnosis {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
            </h4>
            <p>{diagnosis}</p>
          </>
        )}

        {nextBestAction && (
          <>
            <h4 className="micro-head">
              Next Best Action {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
            </h4>
            <p style={{ color: "#38bdf8", fontWeight: 500 }}>{nextBestAction}</p>
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
                <div key={i} style={{ borderLeft: `4px solid ${borderCol}`, background: bgCol, padding: "8px 12px", borderRadius: "4px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                    <strong style={{ color: borderCol, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h.highlight_type}</strong>
                    <Badge value={h.severity} tone={h.severity === "High" ? "danger" : "warn"} />
                  </div>
                  <p style={{ fontStyle: "italic", margin: "4px 0", color: "#e2e8f0", fontSize: "0.95rem" }}>"{h.text}"</p>
                  <p className="muted small" style={{ margin: "4px 0 2px" }}><strong>Why:</strong> {h.reason}</p>
                  <p className="muted small" style={{ margin: 0, color: "#a78bfa" }}><strong>Suggest:</strong> {h.suggested_revision}</p>
                </div>
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
              Suggested Revision Wording {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
            </h4>
            <ul className="bare-list">
              {suggestedWording.map((wording, i) => (
                <li key={i} style={{ fontFamily: "monospace", fontSize: "0.9em", color: "#a78bfa", background: "#2e1065", padding: "4px 8px", borderRadius: "4px", marginBottom: "4px" }}>
                  {wording}
                </li>
              ))}
            </ul>
          </>
        )}

        {defenseQs.length > 0 && (
          <>
            <h4 className="micro-head">
              Top 3 Defense Questions {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
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
                        <td>{Number(e["Similarity Score"] || e.similarity_score).toFixed(3)}</td>
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
    <section className="panel">
      <h2 className="panel-title">Generated Report</h2>
      <a
        className="btn-primary download-link"
        href={`${API_BASE_URL}/download-report/${filename}`}
        target="_blank"
        rel="noreferrer"
      >
        Download PDF Report
      </a>
      <p className="muted small" style={{ marginTop: 6 }}>
        {filename}
      </p>
    </section>
  );
}

/* ───────────────────────── Section Result Panel ───────────────────────── */

function ContextualHighlightsPanel({ highlights = [] }) {
  return (
    <section className="panel">
      <h2 className="panel-title">Contextual Highlights</h2>
      {highlights.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
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
              <div key={i} style={{ borderLeft: `4px solid ${borderCol}`, background: bgCol, padding: "8px 12px", borderRadius: "4px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                  <strong style={{ color: borderCol, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h.highlight_type}</strong>
                  <Badge value={h.severity} tone={h.severity === "High" ? "danger" : "warn"} />
                </div>
                <p style={{ fontStyle: "italic", margin: "4px 0", color: "#e2e8f0", fontSize: "0.95rem" }}>"{h.text}"</p>
                <p className="muted small" style={{ margin: "4px 0 2px" }}><strong>Why:</strong> {h.reason}</p>
                <p className="muted small" style={{ margin: 0, color: "#a78bfa" }}><strong>Suggest:</strong> {h.suggested_revision}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted small">No major overclaim or vague evidence highlights detected.</p>
      )}
    </section>
  );
}

function SectionResultPanel({ result, prevResult }) {
  const isGemini = result.feedback_mode === "Gemini-grounded";
  const diagnosis = isGemini && result.dynamic_diagnosis ? result.dynamic_diagnosis : result.plain_language_diagnosis;
  const nextBestAction = isGemini && result.dynamic_next_best_action ? result.dynamic_next_best_action : result.next_best_action;
  const highlights = result.contextual_highlights || [];
  const suggestedWording = isGemini && result.dynamic_suggested_revision_wording
    ? result.dynamic_suggested_revision_wording
    : result.suggested_revision_wording || [];

  return (
    <>
      <ExecutiveSummary result={result} />
      {diagnosis && (
        <section className="panel">
          <h2 className="panel-title">
            Diagnosis {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
          </h2>
          <p>{diagnosis}</p>
          {result.score_summary && <p className="muted small">{result.score_summary}</p>}
        </section>
      )}
      {nextBestAction && (
        <section className="panel">
          <h2 className="panel-title">
            Next Best Action {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
          </h2>
          <p style={{ color: "#38bdf8", fontWeight: 500 }}>{nextBestAction}</p>
        </section>
      )}
      <ContextualHighlightsPanel highlights={highlights} isGemini={isGemini} />
      <EvidenceCoveragePanel result={result} isManuscript={false} prevResult={prevResult} />
      <RecommendationsPanel
        priorityFixes={result.priority_fixes}
        revisions={isGemini && result.dynamic_suggested_revision_wording ? result.dynamic_suggested_revision_wording : result.revision_suggestions}
        suggestedWording={suggestedWording}
        defenseQs={isGemini && result.dynamic_defense_questions ? result.dynamic_defense_questions : result.defense_questions}
        isGemini={isGemini}
      />
      <DownloadReportPanel filename={result.report_filename} />
    </>
  );
}

function RecommendationsPanel({ priorityFixes = [], revisions = [], suggestedWording = [], defenseQs = [], isGemini = false }) {
  if (!priorityFixes.length && !revisions.length && !suggestedWording.length && !defenseQs.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Recommendations &amp; Defense Prep</h2>

      {priorityFixes.length > 0 && (
        <>
          <h3 className="subhead">Priority Fixes</h3>
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
        </>
      )}

      {revisions.length > 0 && (
        <>
          <h3 className="subhead">
            Revision Suggestions {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
          </h3>
          <ul className="bare-list">
            {revisions.slice(0, 5).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}

      {suggestedWording.length > 0 && (
        <>
          <h3 className="subhead">
            Suggested Revision Wording {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
          </h3>
          <ul className="bare-list">
            {suggestedWording.slice(0, 3).map((w, i) => (
              <li key={i} style={{ fontFamily: "monospace", fontSize: "0.9em", color: "#a78bfa", background: "#2e1065", padding: "4px 8px", borderRadius: "4px", marginBottom: "4px" }}>
                {w}
              </li>
            ))}
          </ul>
        </>
      )}

      {defenseQs.length > 0 && (
        <>
          <h3 className="subhead">
            Likely Defense Questions {isGemini && <span title="AI Generated" style={{ fontSize: '0.8em', marginLeft: '4px' }}>✨</span>}
          </h3>
          <ul className="bare-list">
            {defenseQs.slice(0, 5).map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </>
      )}
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
                          ? "#4ade80"
                          : row.score_change < -0.001
                          ? "#f87171"
                          : "#94a3b8"
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
                <tr style={{ fontWeight: 600, borderTop: "2px solid #1f2d4d" }}>
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
