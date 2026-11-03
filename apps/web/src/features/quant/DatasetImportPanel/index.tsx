import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Button, Form, Input, Select } from 'antd';
import { quantApi } from '../../../api/quant';
import type { DatasetAudit as AuditData, DatasetInput, QuantDataset } from '../../../api/quant';
import { ErrorNotice } from '../../../components/ErrorNotice';
import { DatasetAudit } from '../DatasetAudit';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

export function DatasetImportPanel({
  onImported,
}: {
  onImported: (data: QuantDataset) => Promise<void>;
}) {
  const [file, setFile] = useState('');
  const [fileError, setFileError] = useState<Error | null>(null);
  const [preview, setPreview] = useState<{ payload: DatasetInput; audit: AuditData } | null>(null);
  const [uploadForm] = Form.useForm<Omit<DatasetInput, 'content'>>();
  const imported = useMutation({
    mutationFn: quantApi.import,
    onSuccess: async (data) => {
      setPreview(null);
      await onImported(data);
    },
  });
  const check = useMutation({
    mutationFn: quantApi.preview,
    onSuccess: (audit, payload) => setPreview({ audit, payload }),
  });
  async function readFile(value?: File) {
    setPreview(null);
    setFile('');
    setFileError(null);
    if (!value) return;
    if (value.size > 20000000) {
      setFileError(new Error('CSV 最多 20 MB、100000 行'));
      return;
    }
    try {
      setFile(await value.text());
    } catch {
      setFileError(new Error('无法读取 CSV 文件'));
    }
  }
  return (
    <section className={`${layout.panel} ${layout.scopePanel}`}>
      <h2>导入自有日线 CSV</h2>
      {[imported.error, check.error, fileError].map((error, i) =>
        error ? <ErrorNotice key={i} error={error} /> : null,
      )}
      <a href="/api/quant/template" download>
        下载量化 CSV 模板
      </a>
      <p>
        UTF-8，至少 30 行。OHLC
        必填；成交量单位为股，实际涨跌停价及交易状态留空时拒绝模拟成交。日期使用
        YYYY-MM-DD，available_at 需带时区。
      </p>
      <Form
        form={uploadForm}
        layout="vertical"
        initialValues={{ adjustment: 'raw', selection: 'manual' }}
        onValuesChange={() => setPreview(null)}
        onFinish={(values) => check.mutate({ ...values, content: file })}
        className={styles.form}
      >
        <Form.Item label="数据集名称" name="name" rules={[{ required: true }]}>
          <Input maxLength={100} />
        </Form.Item>
        <Form.Item label="数据来源说明" name="source" rules={[{ required: true }]}>
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item label="价格口径" name="adjustment">
          <Select
            options={[
              { value: 'raw', label: '不复权（交易仍需实际限制字段）' },
              { value: 'qfq', label: '前复权（仅概率研究）' },
            ]}
          />
        </Form.Item>
        <Form.Item label="证券选择依据" name="selection">
          <Select
            options={[
              { value: 'manual', label: '人工选择 / 案例目录' },
              { value: 'historical_universe', label: '提供者声明为历史范围（系统尚未核验）' },
            ]}
          />
        </Form.Item>
        <input
          aria-label="量化日线 CSV"
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => void readFile(e.target.files?.[0])}
        />
        <Button htmlType="submit" disabled={!file} loading={check.isPending}>
          校验并预览
        </Button>
      </Form>
      {preview && (
        <>
          <DatasetAudit audit={preview.audit} />
          <Button
            type="primary"
            loading={imported.isPending}
            onClick={() => imported.mutate(preview.payload)}
          >
            确认保存数据版本
          </Button>
        </>
      )}
    </section>
  );
}
