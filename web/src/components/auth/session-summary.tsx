'use client';

import {useEffect} from 'react';
import {useRouter} from 'next/navigation';
import {Button} from '@astryxdesign/core/Button';
import {browserRequest} from '@/lib/api/browser';
import {useSessionIdentity} from '@/lib/api/queries';
import {useAuthStore} from '@/lib/auth/auth-store';

export function SessionSummary() {
  const router = useRouter();
  const {data} = useSessionIdentity();
  const setIdentity = useAuthStore((state) => state.setIdentity);
  const clearIdentity = useAuthStore((state) => state.clearIdentity);

  useEffect(() => {
    if (data) setIdentity(data);
  }, [data, setIdentity]);

  async function logout() {
    await browserRequest<{authenticated: false}>('/api/session/logout', {
      method: 'POST',
    });
    clearIdentity();
    router.replace('/login');
    router.refresh();
  }

  return (
    <div className="px-3 py-3">
      <div className="truncate text-xs font-medium">
        {data?.user.name ?? '当前用户'}
      </div>
      <div className="mt-1 truncate text-xs opacity-60">
        {data?.tenant.name ?? '加载租户…'}
      </div>
      <div className="mt-3">
        <Button label="退出登录" variant="ghost" size="sm" onClick={logout} />
      </div>
    </div>
  );
}
