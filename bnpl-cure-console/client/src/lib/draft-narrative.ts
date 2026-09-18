/** Structured lines from a GenAI cure draft (markdown-ish, no HTML). */
export type DraftBlock =
  | { type: 'h'; text: string }
  | { type: 'p'; text: string }
  | { type: 'li'; text: string }
  | { type: 'hr' };

export function parseDraft(text: string): DraftBlock[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const out: DraftBlock[] = [];
  for (const raw of lines) {
    const trimmed = raw.trim();
    if (trimmed === '' ) {
      continue;
    }
    if (trimmed === '---') {
      out.push({ type: 'hr' });
      continue;
    }
    const heading = trimmed.match(/^#{1,3}\s+(.*)$/);
    if (heading) {
      out.push({ type: 'h', text: heading[1] });
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      out.push({ type: 'li', text: bullet[1] });
      continue;
    }
    out.push({ type: 'p', text: trimmed });
  }
  return out;
}
