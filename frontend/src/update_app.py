import sys

with open('App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (
        'import { useEffect, useState } from "react";',
        'import { useEffect, useState, useRef } from "react";'
    ),
    (
        '  const [result, setResult] = useState(null);\n  const [error, setError] = useState("");\n  const [loading, setLoading] = useState(false);',
        '  const [result, setResult] = useState(null);\n  const [error, setError] = useState("");\n  const [loading, setLoading] = useState(false);\n  const prevResultRef = useRef(null);'
    ),
    (
        '  function clearOutput() {\n    setResult(null);\n    setError("");\n  }',
        '  function clearOutput() {\n    if (result) {\n      prevResultRef.current = result;\n    }\n    setResult(null);\n    setError("");\n  }'
    ),
    (
        '      {result && activeTab === "manuscript" && <ManuscriptDashboard result={result} />}\n      {result && activeTab === "section" && <SectionResultPanel result={result} />}',
        '      {result && activeTab === "manuscript" && <ManuscriptDashboard result={result} prevResult={prevResultRef.current} />}\n      {result && activeTab === "section" && <SectionResultPanel result={result} prevResult={prevResultRef.current} />}'
    ),
    (
        'function ManuscriptDashboard({ result }) {',
        'function ManuscriptDashboard({ result, prevResult }) {'
    ),
    (
        '      <EvidenceCoveragePanel rows={result.manuscript_evidence_summary} />',
        '      <EvidenceCoveragePanel result={result} isManuscript={true} prevResult={prevResult} />'
    ),
    (
        'function SectionResultPanel({ result }) {',
        'function SectionResultPanel({ result, prevResult }) {'
    ),
    (
        '      <EvidenceCoveragePanel rows={result.evidence_coverage} />',
        '      <EvidenceCoveragePanel result={result} isManuscript={false} prevResult={prevResult} />'
    )
]

for old, new_ in replacements:
    if old in content:
        content = content.replace(old, new_)
    else:
        print(f'Failed to find: {old[:50]}...')

with open('App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Phase 1 done!')
