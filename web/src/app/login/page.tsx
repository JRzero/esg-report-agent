import {redirect} from 'next/navigation';
import {LoginForm} from '@/components/auth/login-form';
import {hasSessionCookie} from '@/lib/server/service-session';

export default async function LoginPage() {
  if (await hasSessionCookie()) {
    redirect('/projects');
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10">
      <LoginForm />
    </main>
  );
}
