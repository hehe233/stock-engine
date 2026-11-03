import type { JobEvent, ReportPreview } from '../../api/types';

export interface StreamBlock {
  id: string;
  kind: 'model' | 'tool' | 'step';
  title: string;
  time: string;
  reasoning: string;
  content: string;
  done: boolean;
  error?: boolean;
  interrupted?: boolean;
  arguments?: unknown;
  result?: unknown;
}

export function projectEvents(events: JobEvent[]) {
  const blocks: StreamBlock[] = [];
  const indexed = new Map<string, StreamBlock>();
  let preview: ReportPreview = {};
  for (const event of events) {
    const p = event.payload;
    if (['queued', 'running', 'failed', 'cancelled'].includes(event.kind)) {
      for (const previous of blocks) {
        if (!previous.done) previous.interrupted = true;
      }
    }
    const id = `${p.attempt ?? 0}:${p.block_id ?? p.call_id ?? event.id}`;
    let block = indexed.get(id);
    if (event.kind === 'model.start' || event.kind === 'tool.start') {
      block = {
        id,
        kind: event.kind === 'model.start' ? 'model' : 'tool',
        title: p.name ?? p.message ?? 'Agent 分析',
        time: event.created_at,
        reasoning: '',
        content: '',
        done: false,
        arguments: p.arguments,
      };
      blocks.push(block);
      indexed.set(id, block);
    }
    if (block) {
      if (event.kind === 'reasoning.delta') block.reasoning += p.text ?? '';
      if (event.kind === 'content.delta') block.content += p.text ?? '';
      if (['model.end', 'tool.end', 'tool.error'].includes(event.kind)) block.done = true;
      if (event.kind === 'tool.end') block.result = p.result;
      if (event.kind === 'tool.error') {
        block.error = true;
        block.content = p.message ?? '';
      }
    }
    if (event.kind === 'report.patch') preview = { ...preview, ...p.patch };
    if (event.kind === 'report.start') preview = { ...preview, insight: undefined };
    if (event.kind === 'report.delta') {
      preview = { ...preview, insight: p.insight };
      // The structured model's text is also the visible narrative; never expose partial JSON.
      if (block && p.insight) {
        block.content = [
          p.insight.summary ?? '',
          ...(p.insight.observations ?? []).map((item) => (item.text ? `- ${item.text}` : '')),
          ...(p.insight.limitations?.length
            ? ['### 数据局限', ...p.insight.limitations.map((item) => `- ${item}`)]
            : []),
        ]
          .filter(Boolean)
          .join('\n\n');
      }
    }
    if (
      [
        'node',
        'queued',
        'running',
        'failed',
        'cancelled',
        'succeeded',
        'cancel_requested',
      ].includes(event.kind)
    ) {
      blocks.push({
        id: String(event.id),
        kind: 'step',
        title: p.message ?? event.kind,
        time: event.created_at,
        reasoning: '',
        content: p.detail ?? '',
        done: true,
        error: event.kind === 'failed' || event.kind === 'cancelled',
      });
    }
  }
  return { blocks, preview };
}
