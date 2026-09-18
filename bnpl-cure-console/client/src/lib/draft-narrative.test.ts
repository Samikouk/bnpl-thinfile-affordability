import { describe, expect, it } from 'vitest';
import { parseDraft } from './draft-narrative';

describe('parseDraft', () => {
  it('turns markdown headings, bullets, and rules into blocks', () => {
    const blocks = parseDraft(
      '# Early Cure Note\n\n**Your options:**\n- 14-day extension\n---\n*FOR INTERNAL REVIEW ONLY*',
    );
    expect(blocks).toEqual([
      { type: 'h', text: 'Early Cure Note' },
      { type: 'p', text: '**Your options:**' },
      { type: 'li', text: '14-day extension' },
      { type: 'hr' },
      { type: 'p', text: '*FOR INTERNAL REVIEW ONLY*' },
    ]);
  });
});
