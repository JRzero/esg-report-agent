'use client';

import {useMemo, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {
  SegmentedControl,
  SegmentedControlItem,
} from '@astryxdesign/core/SegmentedControl';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useFacts} from '@/lib/api/queries';
import type {FactStatus} from '@/lib/api/types';
import {
  factStatusPresentation,
  formatFactPeriod,
  formatFactValue,
} from '@/lib/facts/fact-policy';
import {FactConflictCenter} from './fact-conflict-center';

type StatusFilter = 'ALL' | FactStatus;

const filters: Array<{value: StatusFilter; label: string}> = [
  {value: 'ALL', label: '全部'},
  {value: 'PENDING', label: '待确认'},
  {value: 'CONFIRMED', label: '已确认'},
  {value: 'CONFLICT', label: '冲突'},
  {value: 'REJECTED', label: '已拒绝'},
];

export function FactCenter({projectId}: {projectId: string}) {
  const query = useFacts(projectId);
  const [status, setStatus] = useState<StatusFilter>('ALL');
  const [search, setSearch] = useState('');

  const facts = query.data ?? [];
  const counts = useMemo(() => {
    const result: Record<StatusFilter, number> = {
      ALL: facts.length,
      PENDING: 0,
      CONFIRMED: 0,
      CONFLICT: 0,
      REJECTED: 0,
    };
    for (const fact of facts) result[fact.status] += 1;
    return result;
  }, [facts]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return facts.filter((fact) => {
      if (status !== 'ALL' && fact.status !== status) return false;
      if (!needle) return true;
      return [
        fact.name,
        fact.semantic_key,
        fact.unit ?? '',
        fact.entity_scope ?? '',
        formatFactValue(fact),
      ]
        .join(' ')
        .toLowerCase()
        .includes(needle);
    });
  }, [facts, search, status]);

  return (
    <div>
      <header>
        <h1 className="text-2xl font-semibold">Fact Center</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
          Fact 是报告写作的业务事实边界。AI 只能产生候选 Fact，正式写作默认只使用人工确认后的 Fact。
        </p>
      </header>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {filters.map((item) => (
          <Card key={item.value} padding={3}>
            <div className="text-xs opacity-50">{item.label}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {counts[item.value]}
            </div>
          </Card>
        ))}
      </div>

      <section className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <SegmentedControl
            label="Fact 状态"
            value={status}
            onChange={(value) => setStatus(value as StatusFilter)}
            size="sm">
            {filters.map((item) => (
              <SegmentedControlItem
                key={item.value}
                value={item.value}
                label={item.label}
              />
            ))}
          </SegmentedControl>

          <TextInput
            label="搜索 Fact"
            isLabelHidden
            value={search}
            onChange={setSearch}
            placeholder="名称、值、范围或 semantic key"
            hasClear
            width={320}
          />
        </div>

        {query.isLoading ? (
          <div className="py-10 text-sm opacity-60">正在加载 Fact…</div>
        ) : null}

        {!query.isLoading && !filtered.length ? (
          <div className="py-10 text-sm opacity-60">
            当前筛选条件下没有 Fact。
          </div>
        ) : null}

        <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {filtered.map((fact) => {
            const state = factStatusPresentation[fact.status];
            return (
              <Card key={fact.id} padding={4}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">
                      {fact.name}
                    </div>
                    <div className="mt-1 truncate text-xs opacity-50">
                      {fact.semantic_key}
                    </div>
                  </div>
                  <Badge label={state.label} variant={state.badge} />
                </div>

                <div className="mt-5 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums">
                    {formatFactValue(fact)}
                  </span>
                  {fact.unit ? (
                    <span className="text-sm opacity-60">{fact.unit}</span>
                  ) : null}
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="opacity-50">期间</div>
                    <div className="mt-1 font-medium">
                      {formatFactPeriod(fact)}
                    </div>
                  </div>
                  <div>
                    <div className="opacity-50">范围</div>
                    <div className="mt-1 font-medium">
                      {fact.entity_scope ?? '未指定'}
                    </div>
                  </div>
                  <div>
                    <div className="opacity-50">来源</div>
                    <div className="mt-1 font-medium">{fact.source_type}</div>
                  </div>
                  <div>
                    <div className="opacity-50">置信度</div>
                    <div className="mt-1 font-medium">
                      {fact.confidence == null
                        ? '—'
                        : `${Math.round(Number(fact.confidence) * 100)}%`}
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <Button
                    label="查看 Fact"
                    variant="secondary"
                    href={`/projects/${projectId}/facts/${fact.id}`}
                  />
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      <div className="mt-10">
        <FactConflictCenter projectId={projectId} />
      </div>
    </div>
  );
}
