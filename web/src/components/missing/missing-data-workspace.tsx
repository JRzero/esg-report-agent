'use client';

import {useMemo, useState, type FormEvent} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {TextArea} from '@astryxdesign/core/TextArea';
import {
  useMissingItems,
  useProjectDisclosures,
  useProjectRequirements,
  useRunMissingAnalysis,
  useUpdateMissingItem,
} from '@/lib/api/queries';
import type {
  MissingItem,
  MissingItemPriority,
  MissingItemStatus,
} from '@/lib/api/types';
import {missingItemStatusLabel} from '@/lib/gri/gri-policy';

const statusVariant: Record<
  MissingItemStatus,
  'error' | 'warning' | 'blue' | 'green' | 'neutral'
> = {
  MISSING: 'error',
  REQUESTED: 'warning',
  RECEIVED: 'blue',
  RESOLVED: 'green',
  NOT_APPLICABLE: 'neutral',
};

function MissingItemEditor({
  projectId,
  item,
  disclosureHref,
  requirementLabel,
}: {
  projectId: string;
  item: MissingItem;
  disclosureHref?: string;
  requirementLabel?: string;
}) {
  const mutation = useUpdateMissingItem(projectId, item.id);
  const [status, setStatus] = useState<MissingItemStatus>(item.status);
  const [priority, setPriority] = useState<MissingItemPriority>(item.priority);
  const [suggestedMaterial, setSuggestedMaterial] = useState(
    item.suggested_material ?? '',
  );
  const [message, setMessage] = useState('');

  async function save(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      await mutation.mutateAsync({
        status,
        priority,
        suggested_material: suggestedMaterial.trim() || null,
      });
      setMessage('Missing Item 已更新。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '更新失败');
    }
  }

  return (
    <Card padding={4}>
      <form onSubmit={save}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold">{item.name}</div>
            {requirementLabel ? (
              <div className="mt-1 text-xs opacity-55">{requirementLabel}</div>
            ) : null}
          </div>
          <Badge label={missingItemStatusLabel[item.status]} variant={statusVariant[item.status]} />
        </div>

        {item.description ? (
          <p className="mt-3 text-sm leading-6 opacity-70">{item.description}</p>
        ) : null}

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Selector
            label="状态"
            value={status}
            onChange={(value) => value && setStatus(value as MissingItemStatus)}
            options={[
              {value: 'MISSING', label: '待补充'},
              {value: 'REQUESTED', label: '已请求'},
              {value: 'RECEIVED', label: '已收到'},
              {value: 'RESOLVED', label: '已解决'},
              {value: 'NOT_APPLICABLE', label: '不适用'},
            ]}
          />
          <Selector
            label="优先级"
            value={priority}
            onChange={(value) => value && setPriority(value as MissingItemPriority)}
            options={[
              {value: 'LOW', label: '低'},
              {value: 'MEDIUM', label: '中'},
              {value: 'HIGH', label: '高'},
            ]}
          />
        </div>

        <div className="mt-4">
          <TextArea
            label="建议补充材料"
            value={suggestedMaterial}
            onChange={setSuggestedMaterial}
            rows={3}
            width="100%"
            isOptional
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            label="保存"
            type="submit"
            variant="secondary"
            isLoading={mutation.isPending}
          />
          {disclosureHref ? (
            <Button
              label="查看 Requirement"
              variant="ghost"
              href={disclosureHref}
            />
          ) : null}
        </div>

        {message ? (
          <div className="mt-3 rounded-md border px-3 py-2 text-sm" role="status">
            {message}
          </div>
        ) : null}
      </form>
    </Card>
  );
}

export function MissingDataWorkspace({projectId}: {projectId: string}) {
  const items = useMissingItems(projectId);
  const requirements = useProjectRequirements(projectId);
  const disclosures = useProjectDisclosures(projectId);
  const analysis = useRunMissingAnalysis(projectId);
  const [filter, setFilter] = useState<'ALL' | MissingItemStatus>('ALL');
  const [message, setMessage] = useState('');

  const requirementById = useMemo(
    () =>
      new Map(
        (requirements.data ?? []).map((requirement) => [
          requirement.requirement_id,
          requirement,
        ]),
      ),
    [requirements.data],
  );

  const projectDisclosureByDisclosureId = useMemo(
    () =>
      new Map(
        (disclosures.data ?? []).map((disclosure) => [
          disclosure.disclosure_id,
          disclosure,
        ]),
      ),
    [disclosures.data],
  );

  const filtered = (items.data ?? []).filter(
    (item) => filter === 'ALL' || item.status === filter,
  );

  const counts = useMemo(() => {
    const result: Record<'ALL' | MissingItemStatus, number> = {
      ALL: items.data?.length ?? 0,
      MISSING: 0,
      REQUESTED: 0,
      RECEIVED: 0,
      RESOLVED: 0,
      NOT_APPLICABLE: 0,
    };
    for (const item of items.data ?? []) result[item.status] += 1;
    return result;
  }, [items.data]);

  async function runAnalysis() {
    setMessage('');
    try {
      const result = await analysis.mutateAsync();
      setMessage(
        `Missing Data Analysis 完成，本次新建 ${result.missing_items_created} 条 Missing Item。`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '缺失分析失败');
    }
  }

  return (
    <div>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">缺失资料</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
            这里管理“需要向企业追什么资料”。收到资料只改变 Missing Item
            工作流，不会直接把 GRI Requirement 标成 COVERED。
          </p>
        </div>
        <Button
          label="运行 Missing Data Analysis"
          variant="primary"
          onClick={runAnalysis}
          isLoading={analysis.isPending}
        />
      </header>

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}

      <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {[
          ['ALL', '全部'],
          ['MISSING', '待补充'],
          ['REQUESTED', '已请求'],
          ['RECEIVED', '已收到'],
          ['RESOLVED', '已解决'],
          ['NOT_APPLICABLE', '不适用'],
        ].map(([key, label]) => (
          <Card key={key} padding={3}>
            <div className="text-xs opacity-50">{label}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {counts[key as 'ALL' | MissingItemStatus]}
            </div>
          </Card>
        ))}
      </section>

      <section className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Missing Items</h2>
            <p className="mt-1 text-sm opacity-60">
              当前列表由 MISSING Requirement 生成，并对活动项保持幂等。
            </p>
          </div>
          <Selector
            label="状态筛选"
            isLabelHidden
            value={filter}
            onChange={(value) =>
              value && setFilter(value as 'ALL' | MissingItemStatus)
            }
            options={[
              {value: 'ALL', label: '全部'},
              {value: 'MISSING', label: '待补充'},
              {value: 'REQUESTED', label: '已请求'},
              {value: 'RECEIVED', label: '已收到'},
              {value: 'RESOLVED', label: '已解决'},
              {value: 'NOT_APPLICABLE', label: '不适用'},
            ]}
            width={180}
          />
        </div>

        {!items.isLoading && !filtered.length ? (
          <div className="py-10 text-sm opacity-60">
            当前筛选条件下没有 Missing Item。
          </div>
        ) : null}

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {filtered.map((item) => {
            const requirement = item.requirement_id
              ? requirementById.get(item.requirement_id)
              : undefined;
            const projectDisclosure = requirement
              ? projectDisclosureByDisclosureId.get(requirement.disclosure_id)
              : undefined;
            return (
              <MissingItemEditor
                key={`${item.id}:${item.updated_at}`}
                projectId={projectId}
                item={item}
                requirementLabel={
                  requirement
                    ? `${requirement.disclosure_code} · Requirement ${requirement.code}`
                    : undefined
                }
                disclosureHref={
                  projectDisclosure
                    ? `/projects/${projectId}/gri/${projectDisclosure.id}`
                    : undefined
                }
              />
            );
          })}
        </div>
      </section>
    </div>
  );
}
