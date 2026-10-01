import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import type {
  MissingItemPriority,
  MissingItemStatus,
} from '@/lib/models/domain';

const priorityVariant: Record<
  MissingItemPriority,
  'neutral' | 'warning' | 'error'
> = {
  LOW: 'neutral',
  MEDIUM: 'warning',
  HIGH: 'error',
};

export type MissingItemCardProps = {
  name: string;
  description: string;
  priority: MissingItemPriority;
  status: MissingItemStatus;
  suggestedMaterial?: string;
};

export function MissingItemCard({
  name,
  description,
  priority,
  status,
  suggestedMaterial,
}: MissingItemCardProps) {
  const priorityLabel = {
    LOW: '低优先级',
    MEDIUM: '中优先级',
    HIGH: '高优先级',
  }[priority];

  return (
    <Card padding={4}>
      <div className="flex items-start justify-between gap-4">
        <div className="text-sm font-semibold">{name}</div>
        <Badge label={priorityLabel} variant={priorityVariant[priority]} />
      </div>

      <p className="mt-3 text-sm leading-6 opacity-75">{description}</p>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs opacity-60">
        <span>状态：{status}</span>
        {suggestedMaterial ? <span>建议材料：{suggestedMaterial}</span> : null}
      </div>
    </Card>
  );
}
