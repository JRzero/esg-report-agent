'use client';

import {useState, type FormEvent} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {TextArea} from '@astryxdesign/core/TextArea';
import {
  useProjectDisclosure,
  useUpdateProjectDisclosure,
} from '@/lib/api/queries';
import type {
  ProjectDisclosure,
  ProjectDisclosureApplicability,
} from '@/lib/api/types';
import {
  disclosureStatusLabel,
  disclosureStatusVariant,
  effectiveDisclosureStatus,
  requirementMetricCodes,
} from '@/lib/gri/gri-policy';
import {formatFactPeriod, formatFactValue} from '@/lib/facts/fact-policy';

function DisclosureSettingsForm({
  projectId,
  disclosure,
}: {
  projectId: string;
  disclosure: ProjectDisclosure;
}) {
  const mutation = useUpdateProjectDisclosure(projectId, disclosure.id);
  const [applicability, setApplicability] =
    useState<ProjectDisclosureApplicability>(disclosure.applicability);
  const [notes, setNotes] = useState(disclosure.notes ?? '');
  const [message, setMessage] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      await mutation.mutateAsync({
        applicability,
        notes: notes.trim() || null,
      });
      setMessage('Disclosure 设置已保存，Requirement Coverage 已按规则刷新。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '保存失败');
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="grid gap-4">
        <Selector
          label="适用性"
          value={applicability}
          onChange={(value) =>
            value && setApplicability(value as ProjectDisclosureApplicability)
          }
          options={[
            {value: 'UNDETERMINED', label: '待判断'},
            {value: 'APPLICABLE', label: '适用'},
            {
              value: 'NOT_APPLICABLE',
              label: '不适用',
              description: '必须由项目人员明确判断，AI 不自动设置。',
            },
          ]}
        />
        <TextArea
          label="适用性说明 / 备注"
          value={notes}
          onChange={setNotes}
          rows={4}
          width="100%"
          isOptional
        />
        <div>
          <Button
            label="保存设置"
            type="submit"
            variant="secondary"
            isLoading={mutation.isPending}
          />
        </div>
        {message ? (
          <div className="rounded-md border px-3 py-2 text-sm" role="status">
            {message}
          </div>
        ) : null}
      </div>
    </form>
  );
}

const requirementVariant: Record<
  string,
  'green' | 'warning' | 'error' | 'neutral'
> = {
  COVERED: 'green',
  PARTIAL: 'warning',
  MISSING: 'error',
  NOT_APPLICABLE: 'neutral',
};

export function DisclosureDetail({
  projectId,
  projectDisclosureId,
}: {
  projectId: string;
  projectDisclosureId: string;
}) {
  const query = useProjectDisclosure(projectId, projectDisclosureId);

  if (query.isLoading || !query.data) {
    return <div className="py-10 text-sm opacity-60">正在加载 Disclosure…</div>;
  }

  const {project_disclosure: disclosure, requirements, fact_maps: factMaps} =
    query.data;
  const effective = effectiveDisclosureStatus(disclosure);

  return (
    <div>
      <header>
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-xs font-medium opacity-55">{disclosure.code}</div>
          <Badge
            label={disclosureStatusLabel(effective)}
            variant={disclosureStatusVariant(effective)}
          />
        </div>
        <h1 className="mt-2 text-2xl font-semibold">{disclosure.title}</h1>
        {disclosure.description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 opacity-65">
            {disclosure.description}
          </p>
        ) : null}
      </header>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <h2 className="text-base font-semibold">Requirements</h2>
          <div className="mt-4 grid gap-4">
            {requirements.map((requirement) => {
              const metricCodes = requirementMetricCodes({
                required_data_json: requirement.required_data_json,
              });
              return (
                <Card key={requirement.id} padding={4}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="text-xs font-medium opacity-55">
                        Requirement {requirement.code} ·{' '}
                        {requirement.requirement_type}
                      </div>
                      <p className="mt-2 text-sm leading-6">
                        {requirement.content}
                      </p>
                    </div>
                    <Badge
                      label={requirement.status}
                      variant={requirementVariant[requirement.status] ?? 'neutral'}
                    />
                  </div>

                  {metricCodes.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {metricCodes.map((code) => (
                        <Badge key={code} label={code} variant="blue" />
                      ))}
                    </div>
                  ) : null}

                  {requirement.reason ? (
                    <div className="mt-4 text-xs opacity-60">
                      {requirement.reason}
                    </div>
                  ) : null}

                  {requirement.guidance ? (
                    <div className="mt-3 rounded-md border px-3 py-2 text-xs leading-5 opacity-70">
                      {requirement.guidance}
                    </div>
                  ) : null}
                </Card>
              );
            })}
          </div>

          <section className="mt-8">
            <h2 className="text-base font-semibold">Mapped Confirmed Facts</h2>
            <p className="mt-1 text-sm opacity-60">
              这里只展示当前仍为 CONFIRMED 的映射 Fact。
            </p>
            {!factMaps.length ? (
              <div className="py-6 text-sm opacity-60">
                当前 Disclosure 没有 mapped Confirmed Fact。
              </div>
            ) : null}
            <div className="mt-4 grid gap-3">
              {factMaps.map(({id, mapping_type, source_type, fact}) => (
                <Card key={id} padding={4}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold">{fact.name}</div>
                      <div className="mt-1 text-xl font-semibold tabular-nums">
                        {formatFactValue(fact)}
                        {fact.unit ? (
                          <span className="ms-1 text-xs font-normal opacity-60">
                            {fact.unit}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 text-xs opacity-55">
                        {formatFactPeriod(fact)} · {fact.entity_scope ?? '未指定范围'}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Badge label={mapping_type} variant="blue" />
                      <Badge label={source_type} variant="neutral" />
                    </div>
                  </div>
                  <div className="mt-4">
                    <Button
                      label="查看 Fact"
                      size="sm"
                      variant="secondary"
                      href={`/projects/${projectId}/facts/${fact.id}`}
                    />
                  </div>
                </Card>
              ))}
            </div>
          </section>
        </div>

        <Card padding={5}>
          <h2 className="text-base font-semibold">项目适用性</h2>
          <p className="mt-1 text-sm leading-6 opacity-60">
            NOT_APPLICABLE 是人工项目判断。设置后 Requirement 会标记为
            NOT_APPLICABLE，并清除 RULE Fact Mapping。
          </p>
          <div className="mt-5">
            <DisclosureSettingsForm
              key={`${disclosure.id}:${disclosure.applicability}:${disclosure.notes ?? ''}`}
              projectId={projectId}
              disclosure={disclosure}
            />
          </div>
        </Card>
      </section>
    </div>
  );
}
