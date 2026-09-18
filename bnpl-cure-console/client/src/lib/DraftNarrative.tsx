import type { ReactNode } from 'react';
import { parseDraft } from './draft-narrative';

function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.filter(Boolean).map((part) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      const inner = part.slice(2, -2);
      return <strong key={`b-${inner}`}>{inner}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      const inner = part.slice(1, -1);
      return <em key={`i-${inner}`}>{inner}</em>;
    }
    return <span key={`t-${part}`}>{part}</span>;
  });
}

export function DraftNarrative({ text }: { text: string }) {
  const blocks = parseDraft(text);
  if (blocks.length === 0) {
    return <p className="text-muted-foreground text-sm">No narrative stored.</p>;
  }
  return (
    <div className="text-muted-foreground space-y-2 text-sm">
      {blocks.map((b) => {
        if (b.type === 'hr') {
          return <hr key={`hr-${b.type}`} className="border-border" />;
        }
        if (b.type === 'h') {
          return (
            <p key={`h-${b.text}`} className="text-foreground font-semibold">
              {inline(b.text)}
            </p>
          );
        }
        if (b.type === 'li') {
          return (
            <p key={`li-${b.text}`} className="pl-4">
              • {inline(b.text)}
            </p>
          );
        }
        return <p key={`p-${b.text}`}>{inline(b.text)}</p>;
      })}
    </div>
  );
}
