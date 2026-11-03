import { authQueries } from '../../features/auth/queries';
import { useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input } from 'antd';
import { authApi } from '../../api/auth';
import { ErrorNotice } from '../ErrorNotice';

export function AuthGate({ children }: { children: ReactNode }) {
  const [key, setKey] = useState('');
  const client = useQueryClient();
  const auth = useQuery({ ...authQueries.status(), staleTime: 0 });
  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: () => {
      setKey('');
      void client.invalidateQueries();
    },
  });
  if (auth.error)
    return (
      <main className="fallback">
        <ErrorNotice error={auth.error} retry={() => void auth.refetch()} />
      </main>
    );
  if (!auth.data)
    return (
      <main className="fallback" role="status">
        正在检查访问状态…
      </main>
    );
  if (auth.data.authenticated) return children;
  return (
    <main className="fallback">
      <h1>访问研究工作台</h1>
      <p>输入后端配置的应用访问密钥。它不是模型 API Key。</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate(key);
        }}
        className={styles.form}
      >
        <Input.Password
          aria-label="应用访问密钥"
          autoComplete="current-password"
          value={key}
          onChange={(event) => setKey(event.target.value)}
        />
        <Button
          htmlType="submit"
          type="primary"
          loading={login.isPending}
          className={styles.submit}
        >
          进入工作台
        </Button>
      </form>
      {login.error && <ErrorNotice error={login.error} />}
    </main>
  );
}
import styles from './index.less';
