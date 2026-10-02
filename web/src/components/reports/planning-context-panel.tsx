'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {useSectionPlanningContext} from '@/lib/api/queries';
import {
  countPlanningContext,
  formatPlanningEvidenceLocator,
} from '@/lib/reports/report-policy';

export function PlanningContextPanel({
  projectId,
  sectionId,
}: {
  projectId: string;
  sectionId: string;
}) {
  const query = useSectionPlanningContext(sectionId);

  if (query.isLoading || !query.data) {
    return <div className="text-sm opacity-60">正在构建 Planning Context…</div>;
  }

  const context = query.data;
  const counts = countPlanningContext(context);

  return (
    <aside className="grid content-start gap-4">
      <Card padding={4}>
        <h2 className="text-sm font-semibold">Planning Context</h2>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
          {Object.entries(counts).map(([key, value]) => (
            <div key={key}>
              <div className="opacity-50">{key}</div>
              <div className="mt-1 text-lg font-semibold">{value}</div>
            </div>
          ))}
        </div>
        {context.warnings.map((warning) => (
          <div key={warning} className="mt-3 rounded-md border px-3 py-2 text-xs">
            {warning}
          </div>
        ))}
      </Card>

      <Card padding={4}>
        <h3 className="text-sm font-semibold">Requirements</h3>
        <div className="mt-3 grid gap-3">
          {context.requirements.map((item) => (
            <div key={item.id} className="rounded-md border px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium">
                  {item.disclosure_code} · {item.code}
                </span>
                <Badge
                  label={item.status}
                  variant={item.status === 'COVERED' ? 'green' : 'error'}
                />
              </div>
              <div className="mt-2 text-xs leading-5 opacity-70">{item.content}</div>
            </div>
          ))}
          {!context.requirements.length ? (
            <div className="text-xs opacity-55">没有绑定 Requirement。</div>
          ) : null}
        </div>
      </Card>

      <Card padding={4}>
        <h3 className="text-sm font-semibold">Confirmed Facts</h3>
        <div className="mt-3 grid gap-3">
          {context.facts.map((fact) => (
            <div key={fact.id} className="rounded-md border px-3 py-2">
              <div className="text-xs font-medium">{fact.name}</div>
              <div className="mt-1 text-sm font-semibold">
                {fact.number_value ?? fact.text_value ?? fact.raw_value ?? '—'}
                {fact.unit ? <span className="ms-1 text-xs opacity-60">{fact.unit}</span> : null}
              </div>
              <div className="mt-2">
                <Button
                  label="查看 Fact"
                  size="sm"
                  variant="ghost"
                  href={`/projects/${projectId}/facts/${fact.id}`}
                />
              </div>
            </div>
          ))}
          {!context.facts.length ? (
            <div className="text-xs opacity-55">当前上下文没有 Confirmed Fact。</div>
          ) : null}
        </div>
      </Card>

      <Card padding={4}>
        <h3 className="text-sm font-semibold">Evidence</h3>
        <div className="mt-3 grid gap-3">
          {context.evidence.slice(0, 12).map((item) => (
            <div key={item.fact_evidence_id} className="rounded-md border px-3 py-2">
              <div className="text-xs font-medium">{item.document_name}</div>
              <div className="mt-1 text-xs opacity-55">
                {formatPlanningEvidenceLocator(item)}
              </div>
              <div className="mt-2 line-clamp-3 text-xs leading-5 opacity-70">
                {item.raw_text}
              </div>
              <div className="mt-2">
                <Button
                  label="查看 Anchor"
                  size="sm"
                  variant="ghost"
                  href={
                    `/projects/${projectId}/materials/${item.document_id}` +
                    `?version=${item.document_version_id}&anchor=${item.anchor_id}`
                  }
                />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {context.missing_items.length ? (
        <Card padding={4}>
          <h3 className="text-sm font-semibold">Missing Warnings</h3>
          <div className="mt-3 grid gap-3">
            {context.missing_items.map((item) => (
              <div key={item.id} className="rounded-md border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium">{item.name}</span>
                  <Badge label={item.priority} variant="warning" />
                </div>
                <div className="mt-2 text-xs leading-5 opacity-70">
                  {item.description}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <Button
              label="打开缺失资料"
              size="sm"
              variant="secondary"
              href={`/projects/${projectId}/missing`}
            />
          </div>
        </Card>
      ) : null}
    </aside>
  );
}
