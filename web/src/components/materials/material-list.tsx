'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {useDocument, useDocuments} from '@/lib/api/queries';
import type {Document} from '@/lib/api/types';
import {materialSourcePolicy} from '@/lib/materials/source-policy';

function MaterialItem({projectId, document}: {projectId: string; document: Document}) {
  const detail = useDocument(document.id);
  const latest = detail.data?.versions[0];
  const source = materialSourcePolicy[document.source_type];

  return (
    <Card padding={4}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{document.name}</div>
          <div className="mt-1 text-xs opacity-60">
            {document.category_code ?? '未分类'}
            {latest ? ` · v${latest.version_no}` : ''}
          </div>
        </div>
        <Badge label={source.label} variant={source.badge} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="opacity-50">Evidence Parse</div>
          <div className="mt-1 font-medium">{latest?.evidence_parse_status ?? '加载中'}</div>
        </div>
        <div>
          <div className="opacity-50">Context</div>
          <div className="mt-1 font-medium">{latest?.context_status ?? '加载中'}</div>
        </div>
      </div>

      {document.source_type === 'REFERENCE' ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-xs">
          Reference 仅用于结构与表达，不作为企业事实证据。
        </div>
      ) : null}

      <div className="mt-4">
        <Button
          label="查看证据"
          variant="secondary"
          href={`/projects/${projectId}/materials/${document.id}`}
        />
      </div>
    </Card>
  );
}

export function MaterialList({projectId}: {projectId: string}) {
  const query = useDocuments(projectId);

  if (query.isLoading) return <div className="py-10 text-sm opacity-60">正在加载资料…</div>;
  if (query.error) return <div className="py-10 text-sm">资料加载失败：{query.error.message}</div>;
  if (!query.data?.length) {
    return (
      <EmptyState
        title="还没有项目资料"
        description="先上传企业 Evidence、历史材料、报告准则或行业 Reference。"
        headingLevel={2}
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      {query.data.map((document) => (
        <MaterialItem key={document.id} projectId={projectId} document={document} />
      ))}
    </div>
  );
}
