'use client';

import {Button} from '@astryxdesign/core/Button';

export type AIActionType =
  | 'rewrite'
  | 'expand'
  | 'shorten'
  | 'regenerate-from-evidence'
  | 'consistency-check';

const labels: Record<AIActionType, string> = {
  rewrite: '改写',
  expand: '扩写',
  shorten: '缩写',
  'regenerate-from-evidence': '根据证据重新生成',
  'consistency-check': '一致性检查',
};

export function AIAction({
  actions,
  onAction,
}: {
  actions: AIActionType[];
  onAction?: (action: AIActionType) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="AI actions">
      {actions.map((action) => (
        <Button
          key={action}
          label={labels[action]}
          variant={action === 'regenerate-from-evidence' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => onAction?.(action)}
        />
      ))}
    </div>
  );
}
