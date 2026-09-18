import { Application, Request, Response } from 'express';
import {
  COHORT_SQL,
  CURE_CASES_SQL,
  DECISIONS_SQL,
  DispositionBody,
  KPI_SQL,
  MerchantParam,
  THRESHOLDS_SQL,
  ThresholdBody,
} from './console-schema';
import { actorEmail } from '../identity';

interface AppKitWithLakebase {
  lakebase: {
    query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  };
  server: { extend(fn: (app: Application) => void): void };
}

function fail(res: Response, status: number, err: unknown) {
  console.error(err);
  const message = status === 400 || status === 401 ? (err as Error).message : 'Request failed';
  res.status(status).json({ error: message });
}

export function setupConsoleRoutes(appkit: AppKitWithLakebase) {
  appkit.server.extend((app) => {
    app.get('/api/whoami', (req: Request, res: Response) => {
      const email = actorEmail(req.header('x-forwarded-email'), process.env.DATABRICKS_USER);
      if (!email) {
        res.status(401).json({ error: 'Signed-in email is required' });
        return;
      }
      res.json({ email });
    });

    app.get('/api/kpis', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(KPI_SQL);
        res.json(rows[0]);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.get('/api/cohorts', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(COHORT_SQL);
        res.json(rows);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.get('/api/decisions', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(DECISIONS_SQL);
        res.json(rows);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.get('/api/thresholds', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(THRESHOLDS_SQL);
        res.json(rows);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.patch('/api/thresholds/:merchant', async (req, res) => {
      const merchant = MerchantParam.safeParse(req.params.merchant);
      const parsed = ThresholdBody.safeParse(req.body);
      const email = actorEmail(req.header('x-forwarded-email'), process.env.DATABRICKS_USER);
      if (!merchant.success || !parsed.success) {
        res.status(400).json({ error: 'Invalid input' });
        return;
      }
      if (!email) {
        res.status(401).json({ error: 'Signed-in email is required' });
        return;
      }
      try {
        const { rows } = await appkit.lakebase.query(
          `UPDATE bnpl.cohort_thresholds
           SET threshold=$1, updated_by=$2, updated_at=NOW()
           WHERE merchant_category=$3
           RETURNING merchant_category, threshold, updated_by, updated_at`,
          [parsed.data.threshold, email, merchant.data],
        );
        if (rows.length === 0) {
          res.status(404).json({ error: 'not found' });
          return;
        }
        res.json(rows[0]);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.get('/api/cure-cases', async (_req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(CURE_CASES_SQL);
        res.json(rows);
      } catch (err) {
        fail(res, 500, err);
      }
    });

    app.post('/api/cure-cases/:id/disposition', async (req, res) => {
      const id = parseInt(req.params.id, 10);
      const parsed = DispositionBody.safeParse(req.body);
      const email = actorEmail(req.header('x-forwarded-email'), process.env.DATABRICKS_USER);
      if (isNaN(id) || !parsed.success) {
        res.status(400).json({ error: 'Invalid input' });
        return;
      }
      if (!email) {
        res.status(401).json({ error: 'Signed-in email is required' });
        return;
      }
      try {
        const { rows } = await appkit.lakebase.query(
          `UPDATE bnpl.cure_cases SET status=$1, disposition=$2, assignee=$3, updated_at=NOW()
           WHERE case_id=$4 RETURNING case_id, status, assignee`,
          [parsed.data.status, parsed.data.disposition ?? null, email, id],
        );
        if (rows.length === 0) {
          res.status(404).json({ error: 'not found' });
          return;
        }
        res.json(rows[0]);
      } catch (err) {
        fail(res, 500, err);
      }
    });
  });
}
