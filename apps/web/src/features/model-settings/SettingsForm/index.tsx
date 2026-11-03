import { modelSettingsQueries } from '../queries';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Form, Input, Select } from 'antd';

import { modelSettingsApi } from '../../../api/model-settings';
import type {
  ModelSettings,
  ModelSettingsInput,
  ModelProfile,
  ModelProfileInput,
} from '../../../api/types';
import { ErrorNotice } from '../../../components/ErrorNotice';
import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

export function SettingsForm({
  initial,
  profile,
  creating,
  disabled,
  onBusy,
  onDirty,
  onSaved,
}: {
  initial: ModelSettings;
  profile?: ModelProfile;
  creating: boolean;
  disabled: boolean;
  onBusy: (busy: boolean) => void;
  onDirty: () => void;
  onSaved: (result: ModelSettings | ModelProfile) => Promise<void>;
}) {
  const [form] = Form.useForm<ModelProfileInput>();
  const client = useQueryClient();
  const [saved, setSaved] = useState(initial);
  const [busy, setBusy] = useState<'save' | 'test' | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const keyAction = Form.useWatch('key_action', form);
  const models = Form.useWatch('models', form) ?? [];

  async function submit(action: 'save' | 'test') {
    let values: ModelProfileInput;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setBusy(action);
    onBusy(true);
    setError(null);
    setNotice(null);
    // 密钥只在提交时从表单读取，不放进 Query/mutation 缓存或浏览器存储。
    const { name, ...fields } = values;
    const payload: ModelSettingsInput = {
      ...fields,
      default_model: values.default_model ?? '',
      models: values.models ?? [],
      revision: saved.revision,
      api_key: values.key_action === 'replace' ? values.api_key : undefined,
    };
    try {
      if (action === 'test') {
        setNotice(
          profile || creating
            ? await modelSettingsApi.testModelProfile({ ...payload, name }, profile?.id)
            : await modelSettingsApi.testModelSettings(payload),
        );
      } else {
        const result =
          profile || creating
            ? await modelSettingsApi.saveModelProfile({ ...payload, name }, profile?.id)
            : await modelSettingsApi.saveModelSettings(payload);
        setSaved(result);
        form.setFieldsValue({ ...result, api_key: '', key_action: 'keep' });
        if (!('active' in result) || result.active)
          client.setQueryData(modelSettingsQueries.settings().queryKey, result);
        await onSaved(result);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason : new Error('操作失败，请重试'));
    } finally {
      setBusy(null);
      onBusy(false);
    }
  }

  return (
    <section className={`${layout.panel} ${layout.scopePanel}`}>
      <Alert
        type="info"
        showIcon
        title="使用你已有的模型 API"
        description="支持 OpenAI 兼容 Chat Completions 和工具调用。保存不会发起模型请求；测试连接会产生一次小型模型调用，费用由服务商决定。"
      />
      <Form<ModelProfileInput>
        form={form}
        layout="vertical"
        name="model-settings"
        initialValues={{
          ...initial,
          name: profile?.name ?? '',
          api_key: '',
          key_action: initial.has_api_key ? 'keep' : 'replace',
        }}
        disabled={busy !== null || disabled}
        onFinish={() => void submit('save')}
        onValuesChange={() => {
          onDirty();
          setNotice(null);
          setError(null);
        }}
        className={styles.form}
      >
        <h2>API 服务</h2>
        {(profile || creating) && (
          <Form.Item
            label="配置名称"
            name="name"
            rules={[{ required: true, whitespace: true, message: '请输入便于识别的配置名称' }]}
          >
            <Input maxLength={80} placeholder="例如：日常研究、备用 API" />
          </Form.Item>
        )}
        <p>
          当前配置：{saved.source === 'saved' ? '页面保存的配置' : '后端环境配置'} · 密钥
          {saved.has_api_key ? '已配置' : '未配置'}
        </p>
        <Form.Item
          label="API 地址（Base URL）"
          name="base_url"
          rules={[
            { required: true, message: '请输入 API 地址' },
            { type: 'url', message: '请输入有效的 http:// 或 https:// 地址' },
          ]}
          extra="通常填写到 /v1，例如 https://api.example.com/v1，不要填写 /chat/completions。"
        >
          <Input placeholder="https://api.example.com/v1" autoComplete="off" />
        </Form.Item>
        <Form.Item label="密钥处理" name="key_action">
          <Select
            options={[
              { value: 'keep', label: '保留已有密钥' },
              { value: 'replace', label: '输入 / 替换密钥' },
              { value: 'clear', label: '清除当前配置的密钥' },
            ]}
          />
        </Form.Item>
        {keyAction === 'replace' && (
          <Form.Item
            label="API Key"
            name="api_key"
            preserve={false}
            rules={[{ required: true, whitespace: true, message: '请输入 API Key' }]}
            extra="保存后不会回显密钥。更换 API 地址时，请同时替换或清除密钥。"
          >
            <Input.Password
              autoComplete="new-password"
              placeholder="输入你的 API Key"
              maxLength={4096}
            />
          </Form.Item>
        )}
        <Form.Item
          label="可选模型"
          name="models"
          extra="输入服务商的准确模型 ID，按回车添加；可配置多个模型。"
        >
          <Select
            mode="tags"
            tokenSeparators={[',', '，']}
            placeholder="输入模型 ID 并按回车"
            options={models.map((name: string) => ({ value: name, label: name }))}
          />
        </Form.Item>
        <Form.Item
          label="默认模型"
          name="default_model"
          dependencies={['models']}
          rules={[
            {
              validator: async (_, value) => {
                if (models.length > 0 && !models.includes(value))
                  throw new Error('请从可选模型中选择默认模型');
              },
            },
          ]}
        >
          <Select
            allowClear
            placeholder="选择默认模型"
            options={models.map((name: string) => ({ value: name, label: name }))}
          />
        </Form.Item>
        <h2>Ollama 备选</h2>
        <p>仅在行情工作台手动选择时使用，API 失败不会自动切换。</p>
        <Form.Item label="Ollama 地址" name="ollama_base_url" rules={[{ required: true }]}>
          <Input placeholder="http://127.0.0.1:11434" />
        </Form.Item>
        <Form.Item label="Ollama 模型" name="ollama_model" rules={[{ required: true }]}>
          <Input placeholder="qwen3:8b" />
        </Form.Item>
        <div className={styles.actions}>
          <Button type="primary" htmlType="submit" loading={busy === 'save'}>
            保存设置
          </Button>
          <Button onClick={() => void submit('test')} loading={busy === 'test'}>
            测试 API 连接
          </Button>
          <Button
            onClick={() => {
              window.location.reload();
            }}
          >
            重新加载设置
          </Button>
        </div>
      </Form>
      {notice && (
        <Alert
          className={styles.notice}
          type={notice.ok ? 'success' : 'error'}
          showIcon
          title={notice.message}
        />
      )}
      {error && <ErrorNotice error={error} />}
      <p className={styles.notice}>已提交任务保留提交时的模型配置；更换配置只影响新任务。</p>
    </section>
  );
}
