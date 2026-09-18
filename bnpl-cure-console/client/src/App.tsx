import { useCallback, useEffect, useState, type ReactNode } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '@databricks/appkit-ui/react';

type Kpis = {
  applications: number;
  approvals: number;
  approval_pct: number;
  fpd_pct: number;
  cures_in_progress: number;
};
type Cohort = {
  merchant_category: string;
  applications: number;
  approvals: number;
  fpd_pct: number;
  approved_fpd_pct: number;
};
type Decision = {
  application_id: string;
  merchant_category: string;
  score: number;
  decision: string;
  reason_codes: string;
  thin_file_flag: number;
};
type Threshold = { merchant_category: string; threshold: number; updated_by: string };
type CureCase = {
  case_id: number;
  application_id: string;
  status: string;
  priority: string;
  assignee: string | null;
  cure_narrative: string | null;
  disposition: string | null;
};

function num(v: unknown): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const refetch = useCallback(() => {
    setLoading(true);
    setTick((t) => t + 1);
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    fetch(path, { signal: ac.signal })
      .then(async (r) => {
        if (!r.ok) {
          throw new Error(`Request failed (${r.status})`);
        }
        return r.json() as Promise<T>;
      })
      .then((body) => {
        setData(body);
        setError(null);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setError(e instanceof Error ? e.message : 'Request failed');
        setLoading(false);
      });
    return () => ac.abort();
  }, [path, tick]);

  return { data, error, loading, refetch };
}

function DecisionBadge({ decision }: { decision: string }) {
  const approve = decision === 'APPROVE';
  return (
    <Badge variant={approve ? 'secondary' : 'destructive'}>
      {approve ? 'APPROVE' : 'DECLINE'}
    </Badge>
  );
}

export default function App() {
  const kpis = useApi<Kpis>('/api/kpis');
  const cohorts = useApi<Cohort[]>('/api/cohorts');
  const decisions = useApi<Decision[]>('/api/decisions');
  const thresholds = useApi<Threshold[]>('/api/thresholds');
  const cures = useApi<CureCase[]>('/api/cure-cases');
  const whoami = useApi<{ email: string }>('/api/whoami');

  const [draftThr, setDraftThr] = useState<Record<string, string>>({});
  const [selectedCase, setSelectedCase] = useState<number | null>(null);
  const [dispStatus, setDispStatus] = useState('IN_PROGRESS');
  const [dispNote, setDispNote] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  async function saveThreshold(merchant: string) {
    setActionError(null);
    setActionBusy(true);
    try {
      const threshold = Number(draftThr[merchant]);
      const r = await fetch(`/api/thresholds/${encodeURIComponent(merchant)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold }),
      });
      if (!r.ok) {
        const body = (await r.json()) as { error?: string };
        throw new Error(body.error ?? `Request failed (${r.status})`);
      }
      thresholds.refetch();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Could not update threshold');
    } finally {
      setActionBusy(false);
    }
  }

  async function saveDisposition(caseId: number) {
    setActionError(null);
    setActionBusy(true);
    try {
      const r = await fetch(`/api/cure-cases/${caseId}/disposition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: dispStatus, disposition: dispNote || undefined }),
      });
      if (!r.ok) {
        const body = (await r.json()) as { error?: string };
        throw new Error(body.error ?? `Request failed (${r.status})`);
      }
      setDispNote('');
      cures.refetch();
      kpis.refetch();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Could not disposition case');
    } finally {
      setActionBusy(false);
    }
  }

  const selected = cures.data?.find((c) => c.case_id === selectedCase) ?? null;

  return (
    <div className="mx-auto max-w-6xl p-4 font-sans">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Approval &amp; Early-Cure Console</h1>
          <p className="text-muted-foreground m-0 text-sm">
            Thin-file BNPL affordability. Source: Lakebase <code>public.decisions</code> and{' '}
            <code>bnpl.*</code>. Approve when score &lt; cohort threshold.
          </p>
        </div>
        {whoami.data?.email && (
          <Badge variant="outline">{whoami.data.email}</Badge>
        )}
      </div>

      {actionError && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>Write-back failed</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Applications"
          value={kpis.data ? String(kpis.data.applications) : null}
          sub="Lakebase decisions, all rows"
          loading={kpis.loading}
          error={kpis.error}
        />
        <KpiCard
          label="Approval rate"
          value={kpis.data ? `${num(kpis.data.approval_pct)}%` : null}
          sub={kpis.data ? `${kpis.data.approvals} approved` : 'share of decisions'}
          loading={kpis.loading}
          error={kpis.error}
        />
        <KpiCard
          label="Approved-book FPD"
          value={kpis.data ? `${num(kpis.data.fpd_pct)}%` : null}
          sub="First-payment default on APPROVE only"
          loading={kpis.loading}
          error={kpis.error}
        />
        <KpiCard
          label="Cures in progress"
          value={kpis.data ? String(kpis.data.cures_in_progress) : null}
          sub="OPEN + IN_PROGRESS"
          loading={kpis.loading}
          error={kpis.error}
        />
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">FPD by merchant cohort</CardTitle>
          <CardDescription>
            Genie surfaces the worst cohort; the analyst tightens that threshold below. Portfolio
            FPD is all applications; approved-book FPD is the loss rate on the book.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState loading={cohorts.loading} error={cohorts.error} empty={!cohorts.loading && !!cohorts.data && cohorts.data.length === 0} emptyTitle="No cohort rows">
            {cohorts.data && (
              <Table>
                <TableCaption>Source: public.decisions grouped by merchant_category</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Merchant</TableHead>
                    <TableHead scope="col">Applications</TableHead>
                    <TableHead scope="col">Approvals</TableHead>
                    <TableHead scope="col">Portfolio FPD</TableHead>
                    <TableHead scope="col">Approved-book FPD</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cohorts.data.map((c) => (
                    <TableRow key={c.merchant_category}>
                      <TableCell>{c.merchant_category}</TableCell>
                      <TableCell>{c.applications}</TableCell>
                      <TableCell>{c.approvals}</TableCell>
                      <TableCell className={num(c.fpd_pct) >= 6 ? 'text-destructive font-medium' : ''}>
                        {num(c.fpd_pct)}%
                        {num(c.fpd_pct) >= 6 ? ' (high)' : ''}
                      </TableCell>
                      <TableCell>{num(c.approved_fpd_pct)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryState>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Decision queue</CardTitle>
          <CardDescription>
            Score is P(FPD). Reason codes are SHAP, not the LLM. Highest scores first.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState loading={decisions.loading} error={decisions.error} empty={!decisions.loading && !!decisions.data && decisions.data.length === 0} emptyTitle="No decisions">
            {decisions.data && (
              <Table>
                <TableCaption>Latest 40 rows from public.decisions</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Application</TableHead>
                    <TableHead scope="col">Merchant</TableHead>
                    <TableHead scope="col">Score</TableHead>
                    <TableHead scope="col">Decision</TableHead>
                    <TableHead scope="col">Reason codes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {decisions.data.map((d) => (
                    <TableRow key={d.application_id}>
                      <TableCell>
                        {d.application_id}
                        {num(d.thin_file_flag) ? (
                          <span className="text-muted-foreground"> · thin-file</span>
                        ) : null}
                      </TableCell>
                      <TableCell>{d.merchant_category}</TableCell>
                      <TableCell>{num(d.score)}</TableCell>
                      <TableCell>
                        <DecisionBadge decision={d.decision} />
                      </TableCell>
                      <TableCell className="max-w-md whitespace-normal">{d.reason_codes}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryState>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cohort thresholds</CardTitle>
            <CardDescription>
              Write-back closes the loop. Next score uses APPROVE if score &lt; threshold.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState loading={thresholds.loading} error={thresholds.error} empty={!thresholds.loading && !!thresholds.data && thresholds.data.length === 0} emptyTitle="No thresholds">
              {thresholds.data && (
                <Table>
                  <TableCaption>Mutable bnpl.cohort_thresholds</TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Merchant</TableHead>
                      <TableHead scope="col">Threshold</TableHead>
                      <TableHead scope="col">Updated by</TableHead>
                      <TableHead scope="col">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {thresholds.data.map((t) => (
                      <TableRow key={t.merchant_category}>
                        <TableCell>{t.merchant_category}</TableCell>
                        <TableCell>
                          <Label className="sr-only" htmlFor={`thr-${t.merchant_category}`}>
                            Threshold for {t.merchant_category}
                          </Label>
                          <Input
                            id={`thr-${t.merchant_category}`}
                            type="number"
                            step="0.01"
                            min={0.01}
                            max={0.99}
                            className="w-24"
                            value={draftThr[t.merchant_category] ?? String(num(t.threshold))}
                            onChange={(e) =>
                              setDraftThr((d) => ({ ...d, [t.merchant_category]: e.target.value }))
                            }
                          />
                        </TableCell>
                        <TableCell className="text-muted-foreground">{t.updated_by}</TableCell>
                        <TableCell>
                          <Button
                            size="sm"
                            disabled={actionBusy}
                            onClick={() => void saveThreshold(t.merchant_category)}
                          >
                            Save
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Early-cure cases</CardTitle>
            <CardDescription>Select a case to read the GenAI draft and disposition it.</CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState loading={cures.loading} error={cures.error} empty={!cures.loading && !!cures.data && cures.data.length === 0} emptyTitle="No cure cases">
              {cures.data && (
                <Table>
                  <TableCaption>bnpl.cure_cases, most recently updated</TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Case</TableHead>
                      <TableHead scope="col">Application</TableHead>
                      <TableHead scope="col">Priority</TableHead>
                      <TableHead scope="col">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cures.data.map((c) => (
                      <TableRow
                        key={c.case_id}
                        className="cursor-pointer"
                        onClick={() => setSelectedCase(c.case_id)}
                      >
                        <TableCell>#{c.case_id}</TableCell>
                        <TableCell>{c.application_id}</TableCell>
                        <TableCell>{c.priority}</TableCell>
                        <TableCell>{c.status}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </QueryState>

            {selected && (
              <div className="mt-4 space-y-3">
                <h2 className="text-sm font-semibold">Case #{selected.case_id} draft (human review)</h2>
                <p className="text-muted-foreground whitespace-pre-wrap text-sm">
                  {selected.cure_narrative || 'No narrative stored.'}
                </p>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="disp-status">Disposition status</Label>
                  <Select value={dispStatus} onValueChange={setDispStatus}>
                    <SelectTrigger id="disp-status" className="w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="OPEN">OPEN</SelectItem>
                      <SelectItem value="IN_PROGRESS">IN_PROGRESS</SelectItem>
                      <SelectItem value="CURED">CURED</SelectItem>
                      <SelectItem value="CLOSED">CLOSED</SelectItem>
                    </SelectContent>
                  </Select>
                  <Label htmlFor="disp-note">Note</Label>
                  <Textarea
                    id="disp-note"
                    value={dispNote}
                    onChange={(e) => setDispNote(e.target.value)}
                    maxLength={2000}
                    placeholder="Analyst outcome note"
                  />
                  <Button disabled={actionBusy} onClick={() => void saveDisposition(selected.case_id)}>
                    Save disposition
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  loading,
  error,
}: {
  label: string;
  value: string | null;
  sub: string;
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-muted-foreground text-xs">{label}</div>
        {loading && <Skeleton className="mt-2 h-8 w-24" />}
        {error && <p className="text-destructive mt-2 text-sm">{error}</p>}
        {!loading && !error && <div className="text-2xl font-semibold">{value ?? '—'}</div>}
        <div className="text-muted-foreground mt-1 text-xs">{sub}</div>
      </CardContent>
    </Card>
  );
}

function QueryState({
  loading,
  error,
  empty,
  emptyTitle,
  children,
}: {
  loading: boolean;
  error: string | null;
  empty: boolean;
  emptyTitle: string;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-5/6" />
        <Skeleton className="h-6 w-2/3" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (empty) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>{emptyTitle}</EmptyTitle>
          <EmptyDescription>Nothing in Lakebase for this view yet.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return <>{children}</>;
}
