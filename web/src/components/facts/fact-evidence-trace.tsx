'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {useFactEvidence} from '@/lib/api/queries';
import type {FactEvidenceTrace as Trace} from '@/lib/api/types';
import {materialSourcePolicy} from '@/lib/materials/source-policy';

function locator(trace: Trace) {
  const anchor = trace.anchor;
  if (anchor.sheet_name || anchor.cell_range) {
    return [
      anchor.sheet_name ? `Sheet: ${anchor.sheet_name}` : null,
      anchor.cell_range ? `Cell: ${anchor.cell_range}` : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  if (anchor.page_start != null) {
    return anchor.page_end != null && anchor.page_end !== anchor.page_start
      ? `Pages ${anchor.page_start}–${anchor.page_end}`
      : `Page ${anchor.page_start}`;
  }
  if (anchor.slide_number != null) return `Slide ${anchor.slide_number}`;
  if (anchor.heading_path?.length) return anchor.heading_path.join(' › ');
  if (anchor.paragraph_start != null) {
    return anchor.paragraph_end != null &&
      anchor.paragraph_end !== anchor.paragraph_start
      ? `Paragraphs ${anchor.paragraph_start}–${anchor.paragraph_end}`
      : `Paragraph ${anchor.paragraph_start}`;
  }
  return anchor.type;
}

export function FactEvidenceTrace({
  projectId,
  factId,
}: {
  projectId: string;
  factId: string;
}) {
  const query = useFactEvidence(factId);

  return (
    <section>
      <h2 className="text-base font-semibold">Evidence Trace</h2>
      <p className="mt-1 text-sm opacity-60">
        每条证据都终止于不可变 DocumentVersion 与 DocumentAnchor。
      </p>

      {query.isLoading ? (
        <div className="py-6 text-sm opacity-60">正在加载 Evidence…</div>
      ) : null}

      {!query.isLoading && !query.data?.length ? (
        <div className="py-6 text-sm opacity-60">当前 Fact 没有关联 Evidence。</div>
      ) : null}

      <div className="mt-4 grid gap-4">
        {(query.data ?? []).map((trace) => {
          const source = materialSourcePolicy[trace.document.source_type];
          const href =
            `/projects/${projectId}/materials/${trace.document.id}` +
            `?version=${encodeURIComponent(trace.document.version_id)}` +
            `&anchor=${encodeURIComponent(trace.anchor.id)}`;

          return (
            <Card key={trace.fact_evidence_id} padding={4}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">
                    {trace.document.name}
                  </div>
                  <div className="mt-1 text-xs opacity-55">
                    v{trace.document.version_no} · {locator(trace)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Badge label={source.label} variant={source.badge} />
                  <Badge label={trace.evidence_role} variant="neutral" />
                </div>
              </div>

              <blockquote className="mt-4 border-s-2 ps-3 text-sm leading-6 opacity-80">
                {trace.anchor.raw_text}
              </blockquote>

              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs opacity-55">
                <span>SHA256 {trace.document.sha256.slice(0, 12)}…</span>
                <span>Anchor {trace.anchor.content_hash.slice(0, 12)}…</span>
              </div>

              <div className="mt-4">
                <Button
                  label="查看原始证据"
                  variant="secondary"
                  size="sm"
                  href={href}
                />
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
