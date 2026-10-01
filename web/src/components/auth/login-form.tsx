'use client';

import {useState, type FormEvent} from 'react';
import {useRouter} from 'next/navigation';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {TextInput} from '@astryxdesign/core/TextInput';
import {ApiError} from '@/lib/api/client';
import {browserRequest} from '@/lib/api/browser';

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await browserRequest<{authenticated: true}>('/api/session/login', {
        method: 'POST',
        body: JSON.stringify({email, password}),
      });
      router.replace('/projects');
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : '登录失败，请检查账号或服务连接。',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card width="100%" maxWidth={440} padding={6}>
      <form onSubmit={submit}>
        <div className="text-xs font-semibold uppercase tracking-widest opacity-50">
          ESG Report Agent
        </div>
        <h1 className="mt-2 text-2xl font-semibold">登录工作台</h1>
        <p className="mt-2 text-sm leading-6 opacity-65">
          使用服务端测试账号登录。认证 Token 仅保存在 HttpOnly Cookie 中。
        </p>

        <div className="mt-6 flex flex-col gap-4">
          <TextInput
            label="邮箱"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            width="100%"
            isRequired
          />
          <TextInput
            label="密码"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            width="100%"
            isRequired
            status={error ? {type: 'error', message: error} : undefined}
            statusVariant="detached"
          />
          <Button
            label="登录"
            type="submit"
            variant="primary"
            width="100%"
            isLoading={isSubmitting}
          />
        </div>
      </form>
    </Card>
  );
}
