import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { JobEvent } from '../../api/types';
import { refreshJob } from '../../features/jobs/queries';

export function useJobStream(id: string, attempt?: number) {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [connection, setConnection] = useState<'connecting' | 'live' | 'reconnecting' | 'done'>(
    'connecting',
  );
  const cursor = useRef(0);
  const client = useQueryClient();
  useEffect(() => {
    if (attempt === undefined) return;
    const stream = new EventSource(
      `/api/jobs/${encodeURIComponent(id)}/events?after=${cursor.current}`,
    );
    let pending: JobEvent[] = [];
    let terminalRefreshed = false;
    const flush = () => {
      if (!pending.length) return;
      const batch = pending;
      pending = [];
      setEvents((current) => [...current, ...batch]);
    };
    const timer = window.setInterval(flush, 40);
    stream.onopen = () => setConnection('live');
    stream.addEventListener('progress', (event: MessageEvent<string>) => {
      try {
        const item = JSON.parse(event.data) as JobEvent;
        if (!Number.isSafeInteger(item.id) || !item.payload || typeof item.kind !== 'string')
          throw new Error('Invalid event');
        if (item.id <= cursor.current) return;
        cursor.current = item.id;
        pending.push(item);
        setConnection('live');
        // Token deltas do not trigger a separate HTTP request for every character.
        if (item.kind === 'running') {
          terminalRefreshed = false;
          void refreshJob(client, id);
        } else if (['succeeded', 'failed', 'cancelled'].includes(item.kind)) {
          terminalRefreshed = true;
          void refreshJob(client, id, true);
        }
      } catch {
        setConnection('reconnecting');
      }
    });
    stream.addEventListener('done', () => {
      flush();
      stream.close();
      setConnection('done');
      if (!terminalRefreshed) void refreshJob(client, id, true);
    });
    stream.onerror = () => setConnection('reconnecting');
    return () => {
      window.clearInterval(timer);
      stream.close();
      flush();
    };
  }, [id, attempt, client]);
  return { events, connection };
}
