'use client';

import {useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {TextArea} from '@astryxdesign/core/TextArea';
import {
  useConfirmFact,
  useFact,
  useRejectFact,
} from '@/lib/api/queries';
import {
  canDirectDecision,
  canEditFact,
  factStatusPresentation,
  formatFactPeriod,
  formatFactValue,
} from '@/lib/facts/fact-policy';
import {FactEditForm} from './fact-edit-form';
import {FactEvidenceTrace} from './fact-evidence-trace';
import {FactRevisionTimeline} from './fact-revision-timeline';

export function FactDetail({
  projectId,
  factId,
}: {
  projectId: string;
  factId: string;
}) {
  const query = useFact(factId);
  const confirm = useConfirmFact(projectId, factId);
  const reject = useRejectFact(projectId, factId);
  const [reason, setReason] = useState('');
  const [message, setMessage] = useState('');

  if (query.isLoading || !query.data) {
    return <div className="py-10 text-sm opacity-60">正在加载 Fact…</div>;
  }

  const fact = query.data;
  const state = factStatusPresentation[fact.status];
  const directDecision = canDirectDecision(fact);

  async function confirmFact() {
    setMessage('');
    try {
      await confirm.mutateAsync();
      setMessage('Fact 已确认。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '确认失败');
    }
  }

  async function rejectFact() {
    if (!reason.trim()) {
      setMessage('拒绝 Fact 时必须填写原因。');
      return;
    }
    setMessage('');
    try {
      await reject.mutateAsync(reason.trim());
      setReason('');
      setMessage('Fact 已拒绝。');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : '拒绝失败');
    }
  }

  return (
    <div>
      <header>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{fact.name}</h1>
          <Badge label={state.label} variant={state.badge} />
          <Badge label={fact.source_type} variant="neutral" />
        </div>
        <div className="mt-2 break-all text-xs opacity-50">
          {fact.semantic_key}
        </div>
      </header>

      <section className="mt-6 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <Card padding={4}>
          <div className="text-xs opacity-50">Fact Value</div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {formatFactValue(fact)}
          </div>
          {fact.unit ? <div className="mt-1 text-sm opacity-60">{fact.unit}</div> : null}
        </Card>
        <Card padding={4}>
          <div className="text-xs opacity-50">期间</div>
          <div className="mt-2 text-sm font-semibold">{formatFactPeriod(fact)}</div>
        </Card>
        <Card padding={4}>
          <div className="text-xs opacity-50">实体范围</div>
          <div className="mt-2 text-sm font-semibold">
            {fact.entity_scope ?? '未指定'}
          </div>
        </Card>
        <Card padding={4}>
          <div className="text-xs opacity-50">置信度</div>
          <div className="mt-2 text-2xl font-semibold">
            {fact.confidence == null
              ? '—'
              : `${Math.round(Number(fact.confidence) * 100)}%`}
          </div>
        </Card>
      </section>

      {fact.status === 'CONFLICT' ? (
        <Card padding={4}>
          <div className="text-sm font-semibold">此 Fact 存在冲突</div>
          <p className="mt-2 text-sm leading-6 opacity-70">
            不能直接确认或拒绝。请返回 Fact Center，在 Conflict Center
            中明确选择最终采用的候选值。
          </p>
          <div className="mt-3">
            <Button
              label="返回 Conflict Center"
              variant="secondary"
              href={`/projects/${projectId}/facts`}
            />
          </div>
        </Card>
      ) : null}

      {directDecision ? (
        <Card padding={5}>
          <h2 className="text-base font-semibold">人工确认</h2>
          <p className="mt-1 text-sm opacity-60">
            Confirm 后 Fact 将进入正式报告可用事实集合，并停止普通 PATCH 编辑。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              label="确认 Fact"
              variant="primary"
              onClick={confirmFact}
              isLoading={confirm.isPending}
            />
          </div>
          <div className="mt-5 max-w-xl">
            <TextArea
              label="拒绝原因"
              value={reason}
              onChange={setReason}
              placeholder="说明为什么该候选 Fact 不应进入事实中心"
              rows={3}
              width="100%"
            />
            <div className="mt-3">
              <Button
                label="拒绝 Fact"
                variant="secondary"
                onClick={rejectFact}
                isLoading={reject.isPending}
              />
            </div>
          </div>
        </Card>
      ) : null}

      {message ? (
        <div className="mt-4 rounded-md border px-3 py-2 text-sm" role="status">
          {message}
        </div>
      ) : null}

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <FactEvidenceTrace projectId={projectId} factId={factId} />
        <div className="grid content-start gap-8">
          {canEditFact(fact) ? (
            <Card padding={5}>
              <FactEditForm projectId={projectId} fact={fact} />
            </Card>
          ) : (
            <Card padding={4}>
              <div className="text-sm font-semibold">Fact 已锁定普通编辑</div>
              <p className="mt-2 text-sm leading-6 opacity-65">
                {fact.status === 'CONFIRMED'
                  ? 'Confirmed Fact 不允许普通 PATCH 修改。需要更正时应拒绝旧 Fact 或创建新的候选 Fact。'
                  : 'Rejected Fact 保留用于审计，不再作为可编辑候选。'}
              </p>
            </Card>
          )}
          <FactRevisionTimeline factId={factId} />
        </div>
      </div>
    </div>
  );
}
