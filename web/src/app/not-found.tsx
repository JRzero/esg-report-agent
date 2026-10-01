import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-xl flex-col justify-center px-6">
      <h1 className="text-xl font-semibold">页面不存在</h1>
      <p className="mt-2 text-sm opacity-70">
        当前路由尚未实现，或资源已经不可用。
      </p>
      <Link className="mt-4 text-sm underline" href="/">
        返回 Foundation
      </Link>
    </div>
  );
}
