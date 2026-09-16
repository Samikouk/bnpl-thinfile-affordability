// Approval & Early-Cure Console routes.
// Reads the synced decisions (public.decisions) + the mutable OLTP tables
// (bnpl.cure_cases, bnpl.cohort_thresholds), and writes case dispositions back.
// The app SP is granted access to these post-deploy (it does not own them).

import { z } from 'zod';
import { Application } from 'express';

interface AppKitWithLakebase {
  lakebase: {
    query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  };
  server: { extend(fn: (app: Application) => void): void };
}

const DispositionBody = z.object({
  status: z.enum(['OPEN', 'IN_PROGRESS', 'CURED', 'CLOSED']),
  disposition: z.string().max(2000).optional(),
});

export async function setupConsoleRoutes(appkit: AppKitWithLakebase) {
  appkit.server.extend((app) => {
    // Portfolio KPIs from the synced decisions
    app.get('/api/kpis', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(`
          SELECT COUNT(*)::int AS applications,
                 SUM(CASE WHEN decision='APPROVE' THEN 1 ELSE 0 END)::int AS approvals,
                 ROUND(AVG(CASE WHEN decision='APPROVE' THEN 1.0 ELSE 0 END)*100, 1) AS approval_pct,
                 ROUND(AVG(fpd_actual)*100, 2) AS fpd_pct
          FROM public.decisions`);
        res.json(rows[0]);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });

    // FPD + approvals by merchant cohort (the Genie-surfaced signal)
    app.get('/api/cohorts', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(`
          SELECT merchant_category,
                 COUNT(*)::int AS applications,
                 SUM(CASE WHEN decision='APPROVE' THEN 1 ELSE 0 END)::int AS approvals,
                 ROUND(AVG(fpd_actual)*100, 2) AS fpd_pct
          FROM public.decisions GROUP BY merchant_category ORDER BY fpd_pct DESC`);
        res.json(rows);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });

    // Recent decision queue with score + reason codes
    app.get('/api/decisions', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(`
          SELECT application_id, merchant_category, ROUND(score::numeric, 3) AS score,
                 decision, reason_codes, thin_file_flag
          FROM public.decisions ORDER BY score DESC LIMIT 40`);
        res.json(rows);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });

    // Per-cohort approval thresholds (mutable)
    app.get('/api/thresholds', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(
          `SELECT merchant_category, threshold, updated_by, updated_at
           FROM bnpl.cohort_thresholds ORDER BY merchant_category`);
        res.json(rows);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });

    // Early-cure case queue (mutable OLTP)
    app.get('/api/cure-cases', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(`
          SELECT case_id, application_id, customer_id, status, priority, assignee,
                 LEFT(COALESCE(cure_narrative,''), 240) AS cure_narrative, updated_at
          FROM bnpl.cure_cases ORDER BY updated_at DESC LIMIT 40`);
        res.json(rows);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });

    // Write-back: analyst dispositions a cure case
    app.post('/api/cure-cases/:id/disposition', async (req, res) => {
      const id = parseInt(req.params.id, 10);
      const parsed = DispositionBody.safeParse(req.body);
      if (isNaN(id) || !parsed.success) { res.status(400).json({ error: 'Invalid input' }); return; }
      try {
        const email = req.header('x-forwarded-email') || 'analyst';
        const { rows } = await appkit.lakebase.query(
          `UPDATE bnpl.cure_cases SET status=$1, disposition=$2, assignee=$3, updated_at=NOW()
           WHERE case_id=$4 RETURNING case_id, status, assignee`,
          [parsed.data.status, parsed.data.disposition ?? null, email, id]);
        if (rows.length === 0) { res.status(404).json({ error: 'not found' }); return; }
        res.json(rows[0]);
      } catch (err) { res.status(500).json({ error: (err as Error).message }); }
    });
  });
}
