'use client';

import {useMemo, useState, type FormEvent} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {TextArea} from '@astryxdesign/core/TextArea';
import {TextInput} from '@astryxdesign/core/TextInput';
import {
  useGenerateSectionPlan,
  useMapSectionDisclosure,
  useProjectDisclosures,
  useProjectTasks,
  useSection,
  useSectionDisclosures,
  useSectionPlanningContext,
  useUnmapSectionDisclosure,
  useUpdateSection,
} from '@/lib/api/queries';
import {WritingPlanEditor} from './writing-plan-editor';
import {PlanningContextPanel} from './planning-context-panel';

export function SectionPlanningWorkspace({
  projectId,
  reportId,
  sectionId,
}: {
  projectId: string;
  reportId: string;
  sectionId: string;
}) {
  const sectionQuery = useSection(sectionId);
  const mappings = useSectionDisclosures(sectionId);
  const projectDisclosures = useProjectDisclosures(projectId);
  const contextQuery = useSectionPlanningContext(sectionId);
  const tasks = useProjectTasks(projectId);
  const update = useUpdateSection(reportId, sectionId);
  const map = useMapSectionDisclosure(reportId, sectionId);
  const unmap = useUnmapSectionDisclosure(reportId, sectionId);
  const generate = useGenerateSectionPlan(projectId, reportId, sectionId);

  const section = sectionQuery.data;
  const [title, setTitle] = useState(section?.title ?? '');
  const [description, setDescription] = useState(section?.description ?? '');
  const [selectedDisclosureId, setSelectedDisclosureId] = useState('');
  const [message, setMessage] = useState('');

  const mappedIds = useMemo(
    () => new Set((mappings.data ?? []).map((item) => item.disclosure_id)),
    [mappings.data],
  );
  const availableDisclosures = (projectDisclosures.data ?? []).filter(
    (item) =>
      item.applicability !== 'NOT_APPLICABLE' &&
      !mappedIds.has(item.disclosure_id),
  );
  const effectiveDisclosureId =
    selectedDisclosureId || availableDisclosures[0]?.disclosure_id || '';

  const planningTask = (tasks.data ?? []).find(
    (task) =>
      task.task_type === 'SECTION_PLANNING' &&
      task.target_id === sectionId,
  );

  if (sectionQuery.isLoading || !section) {
    return <div className="py-10 text-sm opacity-60">正在加载 Section…</div>;
  }

  const effectiveTitle = title || section.title;
  const effectiveDescription =
    description || (section.description ?? '');

  async function saveSection(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      await update.mutateAsync({
        title: effectiveTitle.trim(),
        description: effectiveDescription.trim() || null,
      });
      setTitle('');
      setDescription('');
      setMessage('Section 信息已保存；如上下文发生变化，旧 Writing Plan 已失效。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Section 保存失败');
    }
  }

  async function mapDisclosure() {
    if (!effectiveDisclosureId) return;
    setMessage('');
    try {
      await map.mutateAsync(effectiveDisclosureId);
      setSelectedDisclosureId('');
      setMessage('Disclosure 已绑定；旧 Writing Plan 已失效。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Disclosure Mapping 失败');
    }
  }

  async function generatePlan() {
    setMessage('');
    try {
      const result = await generate.mutateAsync();
      setMessage(`Section Planning 已入队：${result.task_id}`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Section Planning 提交失败');
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <main className="min-w-0">
        <Card padding={5}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">Section</h2>
              <div className="mt-1 text-xs opacity-55">
                level {section.level} · order {section.sort_order}
              </div>
            </div>
            <Badge
              label={section.status}
              variant={section.status === 'GENERATING' ? 'warning' : 'neutral'}
            />
          </div>

          <form className="mt-5 grid gap-4" onSubmit={saveSection}>
            <TextInput
              label="章节标题"
              value={effectiveTitle}
              onChange={setTitle}
              width="100%"
              isRequired
            />
            <TextArea
              label="章节说明"
              value={effectiveDescription}
              onChange={setDescription}
              rows={3}
              width="100%"
              isOptional
            />
            <div>
              <Button
                label="保存 Section"
                type="submit"
                variant="secondary"
                isLoading={update.isPending}
              />
            </div>
          </form>
        </Card>

        <Card padding={5}>
          <h2 className="text-base font-semibold">Disclosure Mapping</h2>
          <p className="mt-1 text-sm opacity-60">
            Section 只能绑定已经挂载到当前项目且非 NOT_APPLICABLE 的 Disclosure。
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            {(mappings.data ?? []).map((item) => (
              <div key={item.mapping_id} className="flex items-center gap-2 rounded-md border px-3 py-2">
                <div>
                  <div className="text-xs font-semibold">{item.code}</div>
                  <div className="text-xs opacity-55">{item.title}</div>
                </div>
                <Button
                  label="移除"
                  size="sm"
                  variant="ghost"
                  onClick={() => unmap.mutate(item.disclosure_id)}
                  isLoading={unmap.isPending}
                />
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-[280px] flex-1">
              <Selector
                label="添加 Disclosure"
                value={effectiveDisclosureId}
                onChange={(value) => value && setSelectedDisclosureId(value)}
                options={availableDisclosures.map((item) => ({
                  value: item.disclosure_id,
                  label: `${item.code} · ${item.title}`,
                  description: `${item.coverage_status} · ${item.applicability}`,
                }))}
                emptyText="没有可添加的 Disclosure"
              />
            </div>
            <Button
              label="绑定"
              variant="secondary"
              onClick={mapDisclosure}
              isDisabled={!effectiveDisclosureId}
              isLoading={map.isPending}
            />
          </div>
        </Card>

        <Card padding={5}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold">AI Section Planning</h2>
              <p className="mt-1 text-sm opacity-60">
                Runtime 只会读取当前 Section 的 Scoped Planning Context。
              </p>
            </div>
            {planningTask ? (
              <Badge
                label={planningTask.status}
                variant={
                  planningTask.status === 'FAILED'
                    ? 'error'
                    : planningTask.status === 'SUCCESS'
                      ? 'green'
                      : 'warning'
                }
              />
            ) : null}
          </div>
          <div className="mt-4">
            <Button
              label={section.status === 'GENERATING' ? '正在生成 Plan' : '生成 Writing Plan'}
              variant="primary"
              onClick={generatePlan}
              isLoading={generate.isPending || section.status === 'GENERATING'}
              isDisabled={section.status === 'GENERATING'}
            />
          </div>
          {planningTask?.error_message ? (
            <div className="mt-3 rounded-md border px-3 py-2 text-sm">
              {planningTask.error_message}
            </div>
          ) : null}
        </Card>

        {message ? (
          <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
            {message}
          </div>
        ) : null}

        {contextQuery.data ? (
          <div className="mt-6">
            <WritingPlanEditor
              key={`${section.id}:${section.writing_plan.version ?? 0}`}
              reportId={reportId}
              section={section}
              context={contextQuery.data}
            />
          </div>
        ) : null}
      </main>

      <PlanningContextPanel projectId={projectId} sectionId={sectionId} />
    </div>
  );
}
