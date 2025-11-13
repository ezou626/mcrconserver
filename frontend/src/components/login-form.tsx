import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<'div'>) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { state, login, clearError } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      return;
    }
    await login(username.trim(), password);
  };

  // Navigate to console on successful login
  useEffect(() => {
    if (state.isAuthenticated) {
      navigate('/console');
    }
  }, [state.isAuthenticated, navigate]);

  // Clear error when user starts typing
  useEffect(() => {
    if (state.error) {
      clearError();
    }
  }, [username, password, state.error, clearError]);

  return (
    <div className={cn('flex flex-col gap-6', className)} {...props}>
      <Card>
        <CardHeader>
          <CardTitle>Login to your account</CardTitle>
          <CardDescription>
            Enter your username and password to access the RCON console
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              {state.error && (
                <div className="rounded-md bg-red-50 p-4 text-sm text-red-700 border border-red-200">
                  {state.error}
                </div>
              )}
              <Field>
                <FieldLabel htmlFor="username">Username</FieldLabel>
                <Input
                  id="username"
                  type="text"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={state.isLoading}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={state.isLoading}
                />
              </Field>
              <Field>
                <Button
                  type="submit"
                  disabled={
                    state.isLoading || !username.trim() || !password.trim()
                  }
                  className="w-full"
                >
                  {state.isLoading ? 'Logging in...' : 'Login'}
                </Button>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
