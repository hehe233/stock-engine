export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    // 定时刷新或分析卡住时，页面应进入错误状态，不能无限 loading。
    signal: options?.signal ?? AbortSignal.timeout(30_000),
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    throw new Error(typeof detail === 'string' ? detail : `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}
