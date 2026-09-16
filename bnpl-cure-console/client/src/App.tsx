import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@databricks/appkit-ui/react';

type Kpis = { applications: number; approvals: number; approval_pct: number; fpd_pct: number };
type Cohort = { merchant_category: string; applications: number; approvals: number; fpd_pct: number };
type Decision = {
  application_id: string; merchant_category: string; score: number;
  decision: string; reason_codes: string; thin_file_flag: number;
};
type Threshold = { merchant_category: string; threshold: number; updated_by: string };
type CureCase = {
  case_id: number; application_id: string; status: string; priority: string;
  assignee: string | null; cure_narrative: string | null;
};

function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch(path)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [path]);
  return { data, error };
}

const dc = (d: string) => (d === 'APPROVE' ? '#137333' : '#b3261e');

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div style={{ fontSize: 12, color: 'var(--muted-foreground, #6b7280)' }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 700 }}>{value}</div>
        {sub && <div style={{ fontSize: 12, color: '#6b7280' }}>{sub}</div>}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card style={{ marginTop: 16 }}>
      <CardHeader><CardTitle style={{ fontSize: 15 }}>{title}</CardTitle></CardHeader>
      <CardContent style={{ overflowX: 'auto' }}>{children}</CardContent>
    </Card>
  );
}

const th: React.CSSProperties = { textAlign: 'left', padding: '6px 10px', fontSize: 12, color: '#6b7280', borderBottom: '1px solid #e5e7eb', whiteSpace: 'nowrap' };
const td: React.CSSProperties = { padding: '6px 10px', fontSize: 13, borderBottom: '1px solid #f3f4f6', whiteSpace: 'nowrap' };

export default function App() {
  const kpis = useApi<Kpis>('/api/kpis');
  const cohorts = useApi<Cohort[]>('/api/cohorts');
  const decisions = useApi<Decision[]>('/api/decisions');
  const thresholds = useApi<Threshold[]>('/api/thresholds');
  const cures = useApi<CureCase[]>('/api/cure-cases');

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 16, fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 2 }}>Approval &amp; Early-Cure Console</h1>
      <p style={{ color: '#6b7280', marginTop: 0 }}>Thin-file BNPL affordability decisioning, backed by Lakebase.</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 12 }}>
        <Kpi label="Applications" value={kpis.data ? String(kpis.data.applications) : '—'} />
        <Kpi label="Approval rate" value={kpis.data ? `${kpis.data.approval_pct}%` : '—'} sub={kpis.data ? `${kpis.data.approvals} approved` : ''} />
        <Kpi label="First-payment default" value={kpis.data ? `${kpis.data.fpd_pct}%` : '—'} sub="portfolio" />
      </div>

      <Section title="First-payment default by merchant cohort (Genie surfaces the worst; analyst re-thresholds it)">
        {cohorts.error && <div style={{ color: dc('DECLINE') }}>Error: {cohorts.error}</div>}
        {!cohorts.data && !cohorts.error && <div>Loading…</div>}
        {cohorts.data && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead><tr><th style={th}>Merchant</th><th style={th}>Applications</th><th style={th}>Approvals</th><th style={th}>FPD %</th></tr></thead>
            <tbody>
              {cohorts.data.map((c) => (
                <tr key={c.merchant_category}>
                  <td style={td}>{c.merchant_category}</td><td style={td}>{c.applications}</td>
                  <td style={td}>{c.approvals}</td>
                  <td style={{ ...td, fontWeight: 600, color: c.fpd_pct >= 6 ? dc('DECLINE') : '#111' }}>{c.fpd_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="Decision queue — score, reason codes, decision">
        {decisions.data && decisions.data.length === 0 && <div>No decisions.</div>}
        {decisions.data && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead><tr><th style={th}>Application</th><th style={th}>Merchant</th><th style={th}>Score</th><th style={th}>Decision</th><th style={th}>Reason codes</th></tr></thead>
            <tbody>
              {decisions.data.map((d) => (
                <tr key={d.application_id}>
                  <td style={td}>{d.application_id}{d.thin_file_flag ? ' · thin-file' : ''}</td>
                  <td style={td}>{d.merchant_category}</td>
                  <td style={td}>{d.score}</td>
                  <td style={{ ...td, fontWeight: 600, color: dc(d.decision) }}>{d.decision}</td>
                  <td style={{ ...td, whiteSpace: 'normal', maxWidth: 380, color: '#374151' }}>{d.reason_codes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <Section title="Cohort thresholds (write-back closes the loop)">
          {thresholds.data && (
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead><tr><th style={th}>Merchant</th><th style={th}>Threshold</th><th style={th}>Updated by</th></tr></thead>
              <tbody>
                {thresholds.data.map((t) => (
                  <tr key={t.merchant_category}>
                    <td style={td}>{t.merchant_category}</td><td style={td}>{t.threshold}</td>
                    <td style={{ ...td, color: '#6b7280' }}>{t.updated_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        <Section title="Early-cure case queue (mutable OLTP)">
          {cures.data && cures.data.length === 0 && <div style={{ color: '#6b7280' }}>No open cure cases.</div>}
          {cures.data && cures.data.length > 0 && (
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead><tr><th style={th}>Case</th><th style={th}>Application</th><th style={th}>Priority</th><th style={th}>Status</th></tr></thead>
              <tbody>
                {cures.data.map((c) => (
                  <tr key={c.case_id}>
                    <td style={td}>#{c.case_id}</td><td style={td}>{c.application_id}</td>
                    <td style={td}>{c.priority}</td><td style={td}>{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      </div>
    </div>
  );
}
