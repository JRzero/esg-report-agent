'use client';

import {useState, type FormEvent} from 'react';
import {Button} from '@astryxdesign/core/Button';
import {Selector} from '@astryxdesign/core/Selector';
import {TextArea} from '@astryxdesign/core/TextArea';
import {TextInput} from '@astryxdesign/core/TextInput';
import {useUpdateFact} from '@/lib/api/queries';
import type {Fact} from '@/lib/api/types';
import {
  buildFactUpdateInput,
  factToEditValues,
} from '@/lib/facts/fact-policy';

export function FactEditForm({
  projectId,
  fact,
}: {
  projectId: string;
  fact: Fact;
}) {
  const update = useUpdateFact(projectId, fact.id);
  const [values, setValues] = useState(() => factToEditValues(fact));
  const [message, setMessage] = useState('');
  const isConflict = fact.status === 'CONFLICT';

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    const result = buildFactUpdateInput(fact, values);
    if (!result.ok) {
      setMessage(result.message);
      return;
    }
    try {
      await update.mutateAsync(result.value);
      setMessage(
        isConflict
          ? '候选值已更新。冲突仍需在 Conflict Center 显式解决。'
          : 'Fact 已更新。',
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Fact 更新失败');
    }
  }

  const valueControl =
    fact.value_type === 'JSON' ? (
      <TextArea
        label="Fact 值"
        value={values.value}
        onChange={(value) => setValues((current) => ({...current, value}))}
        rows={6}
        width="100%"
      />
    ) : fact.value_type === 'BOOLEAN' ? (
      <Selector
        label="Fact 值"
        value={values.value}
        onChange={(value) =>
          value && setValues((current) => ({...current, value}))
        }
        options={[
          {value: 'true', label: '是 / true'},
          {value: 'false', label: '否 / false'},
        ]}
      />
    ) : (
      <TextInput
        label="Fact 值"
        value={values.value}
        onChange={(value) => setValues((current) => ({...current, value}))}
        width="100%"
        isRequired
      />
    );

  return (
    <form onSubmit={submit}>
      <h2 className="text-base font-semibold">编辑 Fact</h2>
      {isConflict ? (
        <p className="mt-1 text-xs leading-5 opacity-60">
          冲突候选只允许修改值和单位；名称、期间、范围属于 semantic key
          边界，必须保持不变并通过 Conflict Center 决策。
        </p>
      ) : null}

      <div className="mt-4 grid gap-4">
        <TextInput
          label="名称"
          value={values.name}
          onChange={(name) => setValues((current) => ({...current, name}))}
          width="100%"
          isDisabled={isConflict}
          disabledMessage="冲突候选不能修改 semantic-key 字段"
        />

        {valueControl}

        <TextInput
          label="单位"
          value={values.unit}
          onChange={(unit) => setValues((current) => ({...current, unit}))}
          width="100%"
          isOptional
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput
            label="期间开始"
            value={values.periodStart}
            onChange={(periodStart) =>
              setValues((current) => ({...current, periodStart}))
            }
            width="100%"
            isDisabled={isConflict}
            disabledMessage="冲突候选不能修改 semantic-key 字段"
            isOptional
          />
          <TextInput
            label="期间结束"
            value={values.periodEnd}
            onChange={(periodEnd) =>
              setValues((current) => ({...current, periodEnd}))
            }
            width="100%"
            isDisabled={isConflict}
            disabledMessage="冲突候选不能修改 semantic-key 字段"
            isOptional
          />
        </div>

        <TextInput
          label="实体范围"
          value={values.entityScope}
          onChange={(entityScope) =>
            setValues((current) => ({...current, entityScope}))
          }
          width="100%"
          isDisabled={isConflict}
          disabledMessage="冲突候选不能修改 semantic-key 字段"
          isOptional
        />

        {message ? (
          <div className="rounded-md border px-3 py-2 text-sm" role="status">
            {message}
          </div>
        ) : null}

        <div>
          <Button
            label="保存修改"
            type="submit"
            variant="secondary"
            isLoading={update.isPending}
          />
        </div>
      </div>
    </form>
  );
}
