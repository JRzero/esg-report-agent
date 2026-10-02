'use client';

import {useMemo, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useDocumentAnchors} from '@/lib/api/queries';
import {formatAnchorLocator} from '@/lib/materials/anchor-locator';

export function AnchorViewer({versionId}: {versionId: string}) {
  const [search, setSearch] = useState('');
  const anchors = useDocumentAnchors(versionId);
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return anchors.data ?? [];
    return (anchors.data ?? []).filter((anchor) =>
      [anchor.raw_text, anchor.anchor_type, formatAnchorLocator(anchor)]
        .join(' ')
        .toLowerCase()
        .includes(needle),
    );
  }, [anchors.data, search]);

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">Evidence Anchors</h2>
          <p className="mt-1 text-sm opacity-60">
            以下坐标由 Service Parser 生成，是 Fact/Citation 的权威来源定位。
          </p>
        </div>
        <TextInput
          label="搜索 Anchor"
          isLabelHidden
          value={search}
          onChange={setSearch}
          placeholder="搜索坐标或原文"
          hasClear
          width={280}
        />
      </div>

      {anchors.isLoading ? <div className="py-8 text-sm opacity-60">正在加载 Anchor…</div> : null}
      {!anchors.isLoading && !filtered.length ? (
        <div className="py-8 text-sm opacity-60">当前版本还没有可展示的 Anchor。</div>
      ) : null}

      <div className="mt-4 grid gap-3">
        {filtered.slice(0, 200).map((anchor) => (
          <Card key={anchor.id} padding={4}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge label={anchor.anchor_type} variant="neutral" />
              <span className="text-xs font-medium">{formatAnchorLocator(anchor)}</span>
            </div>
            <div className="mt-3 whitespace-pre-wrap text-sm leading-6 opacity-80">
              {anchor.raw_text}
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
