import { invalidatePortfolio } from '../queries';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Table } from 'antd';

import { portfolioApi } from '../../../api/portfolio';

import type { ImportPreview } from '../../../api/portfolio';

import { ErrorNotice } from '../../../components/ErrorNotice';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

export function PositionImportPanel() {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [fileError, setFileError] = useState<Error | null>(null);
  const [reading, setReading] = useState(false);
  const client = useQueryClient();
  const load = useMutation({
    mutationFn: portfolioApi.import,
    onSuccess: () => {
      setPreview(null);
      void invalidatePortfolio(client);
    },
  });
  async function readFile(file?: File) {
    setPreview(null);
    setFileError(null);
    if (!file) return;
    if (file.size > 200000) {
      setFileError(new Error('CSV 文件不能超过 200 KB'));
      return;
    }
    setReading(true);
    try {
      setPreview(await portfolioApi.preview(await file.text()));
    } catch (error) {
      setFileError(error instanceof Error ? error : new Error('文件读取失败'));
    } finally {
      setReading(false);
    }
  }
  return (
    <section className={`${layout.panel} ${layout.scopePanel}`}>
      {fileError && <ErrorNotice error={fileError} />}
      {load.error && <ErrorNotice error={load.error} />}
      <h2>CSV 导入</h2>
      <a href="/api/portfolio/template" download>
        下载 CSV 模板
      </a>
      <p>UTF-8 编码，最多 500 行。先核对预览，再确认追加；不会覆盖已有持仓。</p>
      <input
        aria-label="导入持仓 CSV"
        type="file"
        accept=".csv,text/csv"
        disabled={reading}
        onChange={(e) => void readFile(e.target.files?.[0])}
      />
      {reading && <p role="status">正在校验 CSV…</p>}
      {preview && (
        <div className={styles.preview}>
          <p>
            有效行 {preview.count}，错误 {preview.errors.length}。
          </p>
          {preview.errors.map((e) => (
            <p key={e.line}>
              第 {e.line} 行：{e.message}
            </p>
          ))}
          <Table
            rowKey={(_, i) => String(i)}
            size="small"
            dataSource={preview.rows}
            columns={[
              { title: '代码', dataIndex: 'symbol' },
              { title: '数量', dataIndex: 'quantity' },
              { title: '成本', dataIndex: 'cost_price' },
              { title: '日期', dataIndex: 'acquired_on' },
              { title: '制度', dataIndex: 'settlement' },
            ]}
            scroll={{ x: 650 }}
            pagination={{ pageSize: 10 }}
          />
          <Button
            type="primary"
            disabled={!preview.valid}
            loading={load.isPending}
            onClick={() => load.mutate(preview.rows)}
          >
            确认追加导入
          </Button>
        </div>
      )}
      {load.isSuccess && (
        <Alert
          type="success"
          title={`导入 ${load.data.inserted} 行，跳过重复 ${load.data.skipped} 行`}
        />
      )}
    </section>
  );
}
