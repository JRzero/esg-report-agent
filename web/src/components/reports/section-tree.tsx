'use client';

import {useState, type FormEvent} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {Selector} from '@astryxdesign/core/Selector';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useCreateSection} from '@/lib/api/queries';
import type {ReportSection} from '@/lib/api/types';
import {buildSectionTree, type SectionTreeNode} from '@/lib/reports/report-policy';

const statusVariant: Record<string, 'neutral' | 'warning' | 'blue' | 'green'> = {
  NOT_STARTED: 'neutral',
  GENERATING: 'warning',
  DRAFT: 'blue',
  COMPLETED: 'green',
};

function TreeItems({
  nodes,
  selectedId,
  onSelect,
  depth = 0,
}: {
  nodes: SectionTreeNode[];
  selectedId: string;
  onSelect: (sectionId: string) => void;
  depth?: number;
}) {
  return (
    <>
      {nodes.map((node) => (
        <div key={node.id}>
          <button
            type="button"
            onClick={() => onSelect(node.id)}
            className={[
              'w-full rounded-md border px-3 py-2 text-start',
              selectedId === node.id ? 'font-semibold' : 'opacity-80',
            ].join(' ')}
            style={{paddingInlineStart: 12 + depth * 16}}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm">{node.title}</span>
              <Badge
                label={node.status}
                variant={statusVariant[node.status] ?? 'neutral'}
              />
            </div>
          </button>
          {node.children.length ? (
            <div className="mt-1">
              <TreeItems
                nodes={node.children}
                selectedId={selectedId}
                onSelect={onSelect}
                depth={depth + 1}
              />
            </div>
          ) : null}
        </div>
      ))}
    </>
  );
}

export function SectionTree({
  reportId,
  sections,
  selectedId,
  onSelect,
}: {
  reportId: string;
  sections: ReportSection[];
  selectedId: string;
  onSelect: (sectionId: string) => void;
}) {
  const create = useCreateSection(reportId);
  const [title, setTitle] = useState('');
  const [parentId, setParentId] = useState('');
  const [message, setMessage] = useState('');
  const tree = buildSectionTree(sections);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setMessage('请输入章节名称');
      return;
    }
    setMessage('');
    try {
      const parent = sections.find((item) => item.id === parentId);
      const created = await create.mutateAsync({
        title: title.trim(),
        parent_id: parentId || null,
        level: parent ? Math.min(parent.level + 1, 9) : 1,
        sort_order: sections.length + 1,
      });
      setTitle('');
      setParentId('');
      onSelect(created.id);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '创建章节失败');
    }
  }

  return (
    <aside>
      <Card padding={4}>
        <h2 className="text-sm font-semibold">Section Tree</h2>
        <div className="mt-4 grid gap-1">
          {tree.length ? (
            <TreeItems nodes={tree} selectedId={selectedId} onSelect={onSelect} />
          ) : (
            <div className="py-5 text-xs opacity-60">还没有章节。</div>
          )}
        </div>

        <form className="mt-6 border-t pt-4" onSubmit={submit}>
          <div className="text-xs font-semibold">新增章节</div>
          <div className="mt-3 grid gap-3">
            <TextInput
              label="章节标题"
              isLabelHidden
              value={title}
              onChange={setTitle}
              placeholder="例如 员工与发展"
              width="100%"
            />
            <Selector
              label="父章节"
              isLabelHidden
              value={parentId}
              onChange={(value) => setParentId(value ?? '')}
              options={[
                {value: '', label: '顶级章节'},
                ...sections.map((section) => ({
                  value: section.id,
                  label: `${'·'.repeat(Math.max(section.level - 1, 0))} ${section.title}`,
                })),
              ]}
            />
            <Button
              label="添加章节"
              type="submit"
              variant="secondary"
              isLoading={create.isPending}
            />
          </div>
          {message ? (
            <div className="mt-3 text-xs" role="status">{message}</div>
          ) : null}
        </form>
      </Card>
    </aside>
  );
}
