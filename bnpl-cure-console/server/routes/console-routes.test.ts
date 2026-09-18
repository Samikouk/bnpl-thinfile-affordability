import { describe, expect, it } from 'vitest';
import { actorEmail } from '../identity';
import { DispositionBody, DECISIONS_SQL, KPI_SQL, MerchantParam, ThresholdBody } from './console-schema';

describe('actorEmail', () => {
  it('requires a real email and does not default to analyst', () => {
    expect(actorEmail(undefined, undefined)).toBeUndefined();
    expect(actorEmail('analyst', undefined)).toBeUndefined();
    expect(actorEmail('sam@databricks.com', undefined)).toBe('sam@databricks.com');
    expect(actorEmail(undefined, 'local@databricks.com')).toBe('local@databricks.com');
  });
});

describe('request bodies', () => {
  it('accepts a valid disposition', () => {
    expect(DispositionBody.parse({ status: 'CURED', disposition: 'plan agreed' }).status).toBe(
      'CURED',
    );
  });

  it('rejects a bogus status', () => {
    expect(DispositionBody.safeParse({ status: 'DONE' }).success).toBe(false);
  });

  it('accepts a unit-interval threshold', () => {
    expect(ThresholdBody.parse({ threshold: 0.15 }).threshold).toBe(0.15);
    expect(ThresholdBody.safeParse({ threshold: 1.2 }).success).toBe(false);
    expect(MerchantParam.parse('Travel')).toBe('Travel');
    expect(MerchantParam.safeParse('travel').success).toBe(false);
  });
});

describe('KPI SQL', () => {
  it('computes FPD on the approved book and counts open cures', () => {
    expect(KPI_SQL).toContain("FILTER (WHERE decision='APPROVE')");
    expect(KPI_SQL).toContain('cures_in_progress');
  });
});

describe('decisions SQL', () => {
  it('pulls both declines and approvals so the queue is not risk-only', () => {
    expect(DECISIONS_SQL).toContain("decision = 'DECLINE'");
    expect(DECISIONS_SQL).toContain("decision = 'APPROVE'");
    expect(DECISIONS_SQL).toContain('UNION ALL');
  });
});
