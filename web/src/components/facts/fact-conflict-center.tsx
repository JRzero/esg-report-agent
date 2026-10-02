'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {
  useFactConflict,
  useFactConflicts,
  useResolveFactConflict,
} from '@/lib/api/queries';
import type {FactConflictGroup} from '@/lib/api/types';
import {formatFactValue} from '@/lib/facts/fact-policy';

function ConflictGroupCard({
  projectId,
  group,
}: {
  projectId: string;
  group: FactConflictGroup;
}) {
  const detail = useFactConflict(group.id);
  const resolve = useResolveFactConflict(projectId, group.id);
  const currentGroup = detail.data?.group ?? group;
  const members = detail.data?.members ?? [];

  return (
    <Card padding={4}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold">Fact 冲突</div>
          <div className="mt-1 break-all text-xs opacity-55">
            {currentGroup.semantic_key}
          </div>
        </div>
        <Badge
          label={currentGroup.status}
          variant={currentGroup.status === 'OPEN' ? 'error' : 'green'}
        />
      </div>

      <div className="mt-4 grid gap-3">
        {members.map((fact) => {
          const selected = currentGroup.resolved_fact_id === fact.id;
          return (
            <div key={fact.id} className="rounded-md border px-3 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">{fact.name}</div>
                  <div className="mt-1 text-lg font-semibold tabular-nums">
                    {formatFactValue(fact)}
                    {fact.unit ? (
                      <span className="ms-1 text-xs font-normal opacity-60">
                        {fact.unit}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-xs opacity-55">
                    {fact.source_type} · {fact.status}
                  </div>
                </div>

                {currentGroup.status === 'OPEN' ? (
                  <Button
                    label="采用此值"
                    variant="secondary"
                    size="sm"
                    isLoading={resolve.isPending}
                    onClick={() => resolve.mutate(fact.id)}
                  />
                ) : selected ? (
                  <Badge label="最终采用" variant="green" />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      {currentGroup.status === 'OPEN' ? (
        <p className="mt-4 text-xs leading-5 opacity-60">
          系统不会自动选择冲突值。点击“采用此值”后，所选 Fact 将 CONFIRMED，
          同组其他 Fact 将 REJECTED。
        </p>
      ) : null}
    </Card>
  );
}

export function FactConflictCenter({projectId}: {projectId: string}) {
  const query = useFactConflicts(projectId);
  const groups = query.data ?? [];
  const open = groups.filter((group) => group.status === 'OPEN');

  if (!groups.length) return null;

  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">Conflict Center</h2>
          <p className="mt-1 text-sm opacity-60">
            同一 semantic key 出现不同值时必须由人工明确决策。
          </p>
        </div>
        <Badge
          label={open.length ? `${open.length} 个待处理` : '无待处理冲突'}
          variant={open.length ? 'error' : 'green'}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {groups.map((group) => (
          <ConflictGroupCard
            key={group.id}
            projectId={projectId}
            group={group}
          />
        ))}
      </div>
    </section>
  );
}
