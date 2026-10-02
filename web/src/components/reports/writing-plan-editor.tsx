'use client';

import {useMemo, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {TextArea} from '@astryxdesign/core/TextArea';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useSaveSectionPlan} from '@/lib/api/queries';
import type {
  ReportSection,
  SectionPlanningContext,
  SectionWritingPlanInput,
  SectionWritingPlanStatus,
} from '@/lib/api/types';

function lines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function ResourceToggle({
  selected,
  label,
  onClick,
}: {
  selected: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      label={label}
      size="sm"
      variant={selected ? 'primary' : 'secondary'}
      onClick={onClick}
    />
  );
}

export function WritingPlanEditor({
  reportId,
  section,
  context,
}: {
  reportId: string;
  section: ReportSection;
  context: SectionPlanningContext;
}) {
  const plan = section.writing_plan;
  const mutation = useSaveSectionPlan(reportId, section.id);

  const [goal, setGoal] = useState(plan.goal ?? '');
  const [structure, setStructure] = useState(
    (plan.recommended_structure ?? []).join('\n'),
  );
  const [keyMessages, setKeyMessages] = useState(
    (plan.key_messages ?? []).join('\n'),
  );
  const [missingText, setMissingText] = useState(
    (plan.missing_items ?? []).join('\n'),
  );
  const [warnings, setWarnings] = useState(
    (plan.warnings ?? []).join('\n'),
  );
  const [disclosureIds, setDisclosureIds] = useState<string[]>(
    plan.disclosure_ids ?? [],
  );
  const [requirementIds, setRequirementIds] = useState<string[]>(
    plan.requirement_ids ?? [],
  );
  const [factIds, setFactIds] = useState<string[]>(plan.fact_ids ?? []);
  const [evidenceAnchorIds, setEvidenceAnchorIds] = useState<string[]>(
    plan.evidence_anchor_ids ?? [],
  );
  const [missingItemIds, setMissingItemIds] = useState<string[]>(
    plan.missing_item_ids ?? [],
  );
  const [message, setMessage] = useState('');

  const currentStatus =
    (plan.status as SectionWritingPlanStatus | undefined) ?? 'DRAFT';

  const contextSets = useMemo(
    () => ({
      disclosure: new Set(context.disclosures.map((item) => item.id)),
      requirement: new Set(context.requirements.map((item) => item.id)),
      fact: new Set(context.facts.map((item) => item.id)),
      evidence: new Set(context.evidence.map((item) => item.anchor_id)),
      missing: new Set(context.missing_items.map((item) => item.id)),
    }),
    [context],
  );

  function toggle(
    value: string,
    current: string[],
    setter: (values: string[]) => void,
  ) {
    setter(
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  }

  async function save(status: SectionWritingPlanStatus) {
    if (!goal.trim()) {
      setMessage('Writing Plan 的目标不能为空');
      return;
    }

    const stale =
      disclosureIds.some((id) => !contextSets.disclosure.has(id)) ||
      requirementIds.some((id) => !contextSets.requirement.has(id)) ||
      factIds.some((id) => !contextSets.fact.has(id)) ||
      evidenceAnchorIds.some((id) => !contextSets.evidence.has(id)) ||
      missingItemIds.some((id) => !contextSets.missing.has(id));
    if (stale) {
      setMessage('当前计划包含已经离开 Section Context 的资源，请刷新后重新选择。');
      return;
    }

    const input: SectionWritingPlanInput = {
      status,
      goal: goal.trim(),
      recommended_structure: lines(structure),
      key_messages: lines(keyMessages),
      disclosure_ids: disclosureIds,
      requirement_ids: requirementIds,
      fact_ids: factIds,
      evidence_anchor_ids: evidenceAnchorIds,
      missing_item_ids: missingItemIds,
      missing_items: lines(missingText),
      warnings: lines(warnings),
    };

    setMessage('');
    try {
      await mutation.mutateAsync(input);
      setMessage(
        status === 'CONFIRMED'
          ? 'Writing Plan 已人工确认，可进入后续 Section Writing。'
          : 'Writing Plan 草稿已保存。',
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Writing Plan 保存失败');
    }
  }

  return (
    <Card padding={5}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">Writing Plan</h2>
          <p className="mt-1 text-sm opacity-60">
            AI Plan 只会保存为 DRAFT。确认前可以删减 Fact、Evidence、
            Requirement 或补充写作结构。
          </p>
        </div>
        <Badge
          label={currentStatus}
          variant={currentStatus === 'CONFIRMED' ? 'green' : 'warning'}
        />
      </div>

      <div className="mt-5 grid gap-4">
        <TextInput
          label="章节目标"
          value={goal}
          onChange={setGoal}
          width="100%"
          isRequired
        />
        <TextArea
          label="推荐结构（每行一项）"
          value={structure}
          onChange={setStructure}
          rows={5}
          width="100%"
          isOptional
        />
        <TextArea
          label="核心信息（每行一项）"
          value={keyMessages}
          onChange={setKeyMessages}
          rows={4}
          width="100%"
          isOptional
        />
      </div>

      <div className="mt-6 grid gap-5">
        <div>
          <div className="text-xs font-semibold">Disclosures</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {context.disclosures.map((item) => (
              <ResourceToggle
                key={item.id}
                selected={disclosureIds.includes(item.id)}
                label={item.code}
                onClick={() => toggle(item.id, disclosureIds, setDisclosureIds)}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs font-semibold">Requirements</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {context.requirements.map((item) => (
              <ResourceToggle
                key={item.id}
                selected={requirementIds.includes(item.id)}
                label={`${item.disclosure_code} · ${item.code}`}
                onClick={() => toggle(item.id, requirementIds, setRequirementIds)}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs font-semibold">Confirmed Facts</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {context.facts.map((item) => (
              <ResourceToggle
                key={item.id}
                selected={factIds.includes(item.id)}
                label={item.name}
                onClick={() => toggle(item.id, factIds, setFactIds)}
              />
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs font-semibold">Evidence Anchors</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {context.evidence.map((item) => (
              <ResourceToggle
                key={item.anchor_id}
                selected={evidenceAnchorIds.includes(item.anchor_id)}
                label={`${item.document_name} · ${item.anchor_type}`}
                onClick={() =>
                  toggle(
                    item.anchor_id,
                    evidenceAnchorIds,
                    setEvidenceAnchorIds,
                  )
                }
              />
            ))}
          </div>
        </div>

        {context.missing_items.length ? (
          <div>
            <div className="text-xs font-semibold">Missing Items</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {context.missing_items.map((item) => (
                <ResourceToggle
                  key={item.id}
                  selected={missingItemIds.includes(item.id)}
                  label={item.name}
                  onClick={() =>
                    toggle(item.id, missingItemIds, setMissingItemIds)
                  }
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <TextArea
          label="缺失信息说明（每行一项）"
          value={missingText}
          onChange={setMissingText}
          rows={4}
          width="100%"
          isOptional
        />
        <TextArea
          label="Warnings（每行一项）"
          value={warnings}
          onChange={setWarnings}
          rows={4}
          width="100%"
          isOptional
        />
      </div>

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        <Button
          label="保存草稿"
          variant="secondary"
          onClick={() => save('DRAFT')}
          isLoading={mutation.isPending}
        />
        <Button
          label="确认 Writing Plan"
          variant="primary"
          onClick={() => save('CONFIRMED')}
          isLoading={mutation.isPending}
        />
      </div>
    </Card>
  );
}
