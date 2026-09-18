import { z } from 'zod';

export const MERCHANT_CATEGORIES = [
  'Fashion',
  'Electronics',
  'Home',
  'Beauty',
  'Gaming',
  'Travel',
  'Fitness',
  'Jewellery',
] as const;

export const DispositionBody = z.object({
  status: z.enum(['OPEN', 'IN_PROGRESS', 'CURED', 'CLOSED']),
  disposition: z.string().max(2000).optional(),
});

export const ThresholdBody = z.object({
  threshold: z.number().gt(0).lt(1),
});

export const MerchantParam = z.enum(MERCHANT_CATEGORIES);

export const KPI_SQL = `
  SELECT COUNT(*)::int AS applications,
         SUM(CASE WHEN decision='APPROVE' THEN 1 ELSE 0 END)::int AS approvals,
         ROUND(AVG(CASE WHEN decision='APPROVE' THEN 1.0 ELSE 0 END)*100, 1)::float AS approval_pct,
         ROUND(AVG(fpd_actual) FILTER (WHERE decision='APPROVE')*100, 2)::float AS fpd_pct,
         (SELECT COUNT(*)::int FROM bnpl.cure_cases
           WHERE status IN ('OPEN','IN_PROGRESS')) AS cures_in_progress
  FROM public.decisions`;

export const COHORT_SQL = `
  SELECT merchant_category,
         COUNT(*)::int AS applications,
         SUM(CASE WHEN decision='APPROVE' THEN 1 ELSE 0 END)::int AS approvals,
         ROUND(AVG(fpd_actual)*100, 2)::float AS fpd_pct,
         ROUND(AVG(fpd_actual) FILTER (WHERE decision='APPROVE')*100, 2)::float AS approved_fpd_pct
  FROM public.decisions GROUP BY merchant_category ORDER BY fpd_pct DESC`;

export const DECISIONS_SQL = `
  SELECT application_id, merchant_category,
         ROUND(score::numeric, 3)::float AS score,
         decision, reason_codes, thin_file_flag::int AS thin_file_flag
  FROM public.decisions ORDER BY score DESC LIMIT 40`;

export const THRESHOLDS_SQL = `
  SELECT merchant_category, threshold::float AS threshold, updated_by, updated_at
  FROM bnpl.cohort_thresholds ORDER BY merchant_category`;

export const CURE_CASES_SQL = `
  SELECT case_id, application_id, customer_id, status, priority, assignee,
         LEFT(COALESCE(cure_narrative,''), 2000) AS cure_narrative,
         disposition, updated_at
  FROM bnpl.cure_cases ORDER BY updated_at DESC LIMIT 40`;
