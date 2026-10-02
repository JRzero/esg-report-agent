'use client';

import {useMemo, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {
  useProjectDisclosures,
  useProjectRequirements,
  useRunDisclosureMapping,
} from '@/lib/api/queries';
import {
  countDisclosureStatuses,
  disclosureStatusLabel,
  disclosureStatusVariant,
  effectiveDisclosureStatus,
} from '@/lib/gri/gri-policy';
import {StandardAttachPanel} from './standard-attach-panel';

export function GriWorkspace({projectId}: {projectId: string}) {
  const disclosures = useProjectDisclosures(projectId);
  const requirements = useProjectRequirements(projectId);
  const mapping = useRunDisclosureMapping(projectId);
  const [message, setMessage] = useState('');

  const counts = useMemo(
    () => countDisclosureStatuses(disclosures.data ?? []),
    [disclosures.data],
  );

  const requirementsByDisclosure = useMemo(() => {
    const map = new Map<
      string,
      {total: number; covered: number; missing: number; notApplicable: number}
    >();
    for (const requirement of requirements.data ?? []) {
      const current = map.get(requirement.disclosure_id) ?? {
        total: 0,
        covered: 0,
        missing: 0,
        notApplicable: 0,
      };
      current.total += 1;
      if (requirement.status === 'COVERED') current.covered += 1;
      if (requirement.status === 'MISSING') current.missing += 1;
      if (requirement.status === 'NOT_APPLICABLE') current.notApplicable += 1;
      map.set(requirement.disclosure_id, current);
    }
    return map;
  }, [requirements.data]);

  async function runMapping() {
    setMessage('');
    try {
      const result = await mapping.mutateAsync();
      setMessage(
        `Fact Mapping 已完成，本次创建 ${result.mappings_created} 条 RULE Mapping。`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Fact Mapping 失败');
    }
  }

  return (
    <div>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">GRI Workspace</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
            Requirement Coverage 只由已确认 Fact 和项目适用性决定。Reference、
            Pending Fact 或收到但尚未确认的资料都不会自动算作覆盖。
          </p>
        </div>
        <Button
          label="重新计算 Fact Mapping"
          variant="primary"
          onClick={runMapping}
          isLoading={mapping.isPending}
        />
      </header>

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}

      <section className="mt-6">
        <StandardAttachPanel projectId={projectId} />
      </section>

      <section className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ['TOTAL', '全部', counts.TOTAL],
          ['COVERED', '已覆盖', counts.COVERED],
          ['PARTIAL', '部分覆盖', counts.PARTIAL],
          ['MISSING', '缺失', counts.MISSING],
          ['NOT_APPLICABLE', '不适用', counts.NOT_APPLICABLE],
        ].map(([key, label, value]) => (
          <Card key={String(key)} padding={3}>
            <div className="text-xs opacity-50">{label}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {value}
            </div>
          </Card>
        ))}
      </section>

      <section className="mt-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold">Project Disclosures</h2>
            <p className="mt-1 text-sm opacity-60">
              点击 Disclosure 查看 Requirement 与 mapped Confirmed Facts。
            </p>
          </div>
          <Button
            label="查看缺失资料"
            variant="secondary"
            href={`/projects/${projectId}/missing`}
          />
        </div>

        {disclosures.isLoading ? (
          <div className="py-10 text-sm opacity-60">正在加载 Disclosure…</div>
        ) : null}

        {!disclosures.isLoading && !disclosures.data?.length ? (
          <div className="py-10 text-sm opacity-60">
            当前项目还没有挂载报告标准。
          </div>
        ) : null}

        <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {(disclosures.data ?? []).map((disclosure) => {
            const effective = effectiveDisclosureStatus(disclosure);
            const requirementStats =
              requirementsByDisclosure.get(disclosure.disclosure_id);
            return (
              <Card key={disclosure.id} padding={4}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-medium opacity-55">
                      {disclosure.code}
                    </div>
                    <div className="mt-1 text-sm font-semibold">
                      {disclosure.title}
                    </div>
                  </div>
                  <Badge
                    label={disclosureStatusLabel(effective)}
                    variant={disclosureStatusVariant(effective)}
                  />
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="opacity-50">Requirement</div>
                    <div className="mt-1 font-medium">
                      {requirementStats?.total ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="opacity-50">Covered</div>
                    <div className="mt-1 font-medium">
                      {requirementStats?.covered ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="opacity-50">Missing</div>
                    <div className="mt-1 font-medium">
                      {requirementStats?.missing ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="opacity-50">Applicability</div>
                    <div className="mt-1 font-medium">
                      {disclosure.applicability}
                    </div>
                  </div>
                </div>

                {disclosure.notes ? (
                  <p className="mt-4 line-clamp-2 text-xs leading-5 opacity-60">
                    {disclosure.notes}
                  </p>
                ) : null}

                <div className="mt-5">
                  <Button
                    label="查看 Disclosure"
                    variant="secondary"
                    href={`/projects/${projectId}/gri/${disclosure.id}`}
                  />
                </div>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}
