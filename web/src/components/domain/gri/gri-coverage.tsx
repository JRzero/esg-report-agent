import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import type {CoverageStatus} from '@/lib/models/domain';

const presentation: Record<
  CoverageStatus,
  {label: string; variant: 'green' | 'warning' | 'error'}
> = {
  COVERED: {label: '已覆盖', variant: 'green'},
  PARTIAL: {label: '部分覆盖', variant: 'warning'},
  MISSING: {label: '缺失', variant: 'error'},
};

export type GRICoverageProps = {
  code: string;
  title: string;
  covered: number;
  total: number;
  status: CoverageStatus;
};

export function GRICoverage({
  code,
  title,
  covered,
  total,
  status,
}: GRICoverageProps) {
  const state = presentation[status];
  const percentage = total === 0 ? 0 : Math.round((covered / total) * 100);

  return (
    <Card padding={4}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-medium opacity-60">{code}</div>
          <div className="mt-1 text-sm font-semibold">{title}</div>
        </div>
        <Badge label={state.label} variant={state.variant} />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <div
          className="h-2 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10"
          role="progressbar"
          aria-label={`${code} coverage`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percentage}>
          <div
            className="h-full rounded-full bg-current opacity-60"
            style={{width: `${percentage}%`}}
          />
        </div>
        <span className="w-12 text-end text-xs tabular-nums">{percentage}%</span>
      </div>

      <div className="mt-2 text-xs opacity-60">
        Requirement {covered} / {total}
      </div>
    </Card>
  );
}
