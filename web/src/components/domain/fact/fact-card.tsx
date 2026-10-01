import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import type {FactStatus} from '@/lib/models/domain';

const statusPresentation: Record<
  FactStatus,
  {label: string; variant: 'green' | 'warning' | 'error' | 'neutral'}
> = {
  CONFIRMED: {label: '已确认', variant: 'green'},
  PENDING: {label: '待确认', variant: 'warning'},
  CONFLICT: {label: '冲突', variant: 'error'},
  REJECTED: {label: '已拒绝', variant: 'neutral'},
};

export type FactCardProps = {
  name: string;
  value: string | number;
  unit?: string;
  period?: string;
  scope?: string;
  status: FactStatus;
  evidenceCount?: number;
};

export function FactCard({
  name,
  value,
  unit,
  period,
  scope,
  status,
  evidenceCount = 0,
}: FactCardProps) {
  const state = statusPresentation[status];

  return (
    <Card padding={4}>
      <div className="flex items-center justify-between gap-4">
        <div className="text-sm font-medium">{name}</div>
        <Badge label={state.label} variant={state.variant} />
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">{value}</span>
        {unit ? <span className="text-sm opacity-60">{unit}</span> : null}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs opacity-60">
        {period ? <span>期间：{period}</span> : null}
        {scope ? <span>范围：{scope}</span> : null}
        <span>Evidence：{evidenceCount}</span>
      </div>
    </Card>
  );
}
