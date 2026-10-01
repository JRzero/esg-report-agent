import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import type {DocumentSourceType} from '@/lib/models/domain';

const sourcePresentation: Record<
  DocumentSourceType,
  {label: string; variant: 'teal' | 'purple' | 'blue' | 'neutral'}
> = {
  EVIDENCE: {label: 'Evidence', variant: 'teal'},
  REFERENCE: {label: 'Reference', variant: 'purple'},
  STANDARD: {label: 'Standard', variant: 'blue'},
  HISTORICAL: {label: 'Historical', variant: 'neutral'},
};

export type EvidenceCardProps = {
  sourceType: DocumentSourceType;
  fileName: string;
  locator: string;
  excerpt: string;
  usedBy?: string;
};

export function EvidenceCard({
  sourceType,
  fileName,
  locator,
  excerpt,
  usedBy,
}: EvidenceCardProps) {
  const source = sourcePresentation[sourceType];

  return (
    <Card padding={4}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{fileName}</div>
          <div className="mt-1 text-xs opacity-60">{locator}</div>
        </div>
        <Badge label={source.label} variant={source.variant} />
      </div>

      <blockquote className="mt-4 border-s-2 ps-3 text-sm leading-6 opacity-80">
        {excerpt}
      </blockquote>

      {usedBy ? (
        <div className="mt-4 text-xs opacity-60">用于：{usedBy}</div>
      ) : null}

      {sourceType === 'REFERENCE' ? (
        <div
          className="mt-4 rounded-md border px-3 py-2 text-xs"
          data-reference-boundary>
          仅可用于结构与写作风格参考，不得作为当前企业事实证据。
        </div>
      ) : null}
    </Card>
  );
}
