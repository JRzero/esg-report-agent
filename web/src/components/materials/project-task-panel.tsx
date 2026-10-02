'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import {useProjectTasks} from '@/lib/api/queries';

const statusVariant: Record<string, 'neutral' | 'warning' | 'green' | 'error'> = {
  PENDING: 'warning',
  RUNNING: 'warning',
  SUCCESS: 'green',
  FAILED: 'error',
  CANCELLED: 'neutral',
};

export function ProjectTaskPanel({projectId}: {projectId: string}) {
  const query = useProjectTasks(projectId);
  const tasks = (query.data ?? [])
    .filter((task) => task.task_type === 'FACT_EXTRACTION')
    .slice(0, 5);

  if (!tasks.length) return null;

  return (
    <section>
      <h2 className="text-base font-semibold">Fact Extraction Tasks</h2>
      <div className="mt-3 grid gap-3">
        {tasks.map((task) => (
          <Card key={task.id} padding={3}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-medium">Fact Extraction</div>
                <div className="mt-1 text-xs opacity-60">
                  {task.stage ?? '等待执行'} · progress {String(task.progress)}
                </div>
                {task.error_message ? (
                  <div className="mt-2 text-xs">{task.error_message}</div>
                ) : null}
              </div>
              <Badge
                label={task.status}
                variant={statusVariant[task.status] ?? 'neutral'}
              />
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
