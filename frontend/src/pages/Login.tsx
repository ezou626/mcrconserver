import { LoginForm } from '@/components/login-form';

export default function Login() {
  return (
    <div className="flex min-h-screen flex-col justify-center">
      <div className="mx-auto w-full max-w-md px-4">
        <LoginForm />
      </div>
    </div>
  );
}
