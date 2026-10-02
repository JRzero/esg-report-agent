'use client';

import {Badge} from '@astryxdesign/core/Badge';
import {Card} from '@astryxdesign/core/Card';
import {useFactRevisions} from '@/lib/api/queries';

export function FactRevisionTimeline({factId}: {factId: string}) {
  const query = useFactRevisions(factId);

  return (
    <section>
      <h2 className="text-base font-semibold">Revision History</h2>
      <p className="mt-1 text-sm opacity-60">
        Fact 变更历史只读追加，不覆盖旧 Revision。
      </p>

      <div className="mt-4 grid gap-3">
        {(query.data ?? []).map((revision) => (
          <Card key={revision.id} padding={3}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-medium">
                  Revision {revision.revision_no}
                </div>
                <div className="mt-1 text-xs opacity-55">
                  {new Date(revision.created_at).toLocaleString()}
                </div>
              </div>
              <Badge label={revision.change_type} variant="neutral" />
            </div>
            <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs opacity-65">
              {JSON.stringify(revision.snapshot, null, 2)}
            </pre>
          </Card>
        ))}
      </div>
    </section>
  );
}
