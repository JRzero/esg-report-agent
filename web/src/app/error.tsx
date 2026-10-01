'use client';

import {Button} from '@astryxdesign/core/Button';

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & {digest?: string};
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-xl flex-col justify-center px-6">
      <h2 className="text-xl font-semibold">页面加载失败</h2>
      <p className="mt-2 text-sm opacity-70">
        {error.message || '发生未知错误，请重试。'}
      </p>
      <div className="mt-4">
        <Button label="重试" variant="primary" onClick={reset} />
      </div>
    </div>
  );
}
