import { SettingsForm } from '../../features/model-settings/SettingsForm';
import {
  modelSettingsQueries,
  invalidateModelSettings,
} from '../../features/model-settings/queries';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Select } from 'antd';
import { Link } from 'react-router-dom';
import { modelSettingsApi } from '../../api/model-settings';

import { ErrorNotice } from '../../components/ErrorNotice';
import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

export function ModelSettingsPage() {
  const settings = useQuery(modelSettingsQueries.settings());
  const profiles = useQuery(modelSettingsQueries.profiles());
  const client = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [formEpoch, setFormEpoch] = useState(0);
  const [formBusy, setFormBusy] = useState(false);
  const [managing, setManaging] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selection = selected ?? profiles.data?.active_id ?? 'current';
  const profile = profiles.data?.items.find((p) => p.id === selection);
  const active = profiles.data?.items.find((p) => p.active);
  const creating = selection === 'new';
  const busy = managing || formBusy;

  function choose(value: string) {
    if (dirty && !window.confirm('当前修改尚未保存，是否放弃修改？')) return;
    setSelected(value);
    setDirty(false);
    setDeleting(false);
    setError(null);
    setNotice(null);
  }
  async function reload() {
    await invalidateModelSettings(client);
  }
  async function manage(action: 'activate' | 'delete') {
    if (!profile) return;
    if (dirty && !window.confirm('当前修改尚未保存，是否放弃修改？')) return;
    setManaging(true);
    setError(null);
    setNotice(null);
    try {
      if (action === 'activate') await modelSettingsApi.activateModelProfile(profile);
      else await modelSettingsApi.deleteModelProfile(profile);
      setDirty(false);
      setDeleting(false);
      if (action === 'delete') setSelected(null);
      await reload();
      setFormEpoch((value) => value + 1);
      setNotice(
        action === 'activate'
          ? `已启用「${profile.name}」，新任务使用这套配置。`
          : '配置已删除；已提交任务仍保留原配置版本。',
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason : new Error('操作失败'));
    } finally {
      setManaging(false);
    }
  }
  const initial =
    creating && settings.data
      ? {
          ...settings.data,
          revision: null,
          has_api_key: false,
          base_url: '',
          default_model: '',
          models: [],
        }
      : (profile ?? (selection === 'current' ? settings.data : undefined));
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>MODEL SETTINGS</div>
          <h1>模型设置</h1>
          <p>管理多套 API 服务与模型列表，按需切换当前启用配置。</p>
        </div>
        <Link to="/">返回行情工作台 →</Link>
      </div>
      {settings.error && (
        <ErrorNotice error={settings.error} retry={() => void settings.refetch()} />
      )}
      {profiles.error && (
        <ErrorNotice error={profiles.error} retry={() => void profiles.refetch()} />
      )}
      {error && <ErrorNotice error={error} />}
      {notice && <Alert type="success" showIcon title={notice} />}
      {profiles.data && (
        <section className={`${layout.panel} ${layout.scopePanel}`}>
          <h2>API 配置管理</h2>
          <p>
            当前启用：
            {active?.name ??
              (settings.data?.source === 'environment' ? '后端环境配置' : '未启用命名配置')}
            。新增配置保存后，请点击「切换启用」。
          </p>
          <div className={styles.actions}>
            <Select
              aria-label="选择配置"
              value={selection}
              disabled={busy}
              className={styles.profileSelect}
              onChange={choose}
              options={[
                ...(!profiles.data.active_id
                  ? [{ value: 'current', label: '当前设置 / 环境默认' }]
                  : []),
                ...profiles.data.items.map((p) => ({
                  value: p.id,
                  label: p.name + (p.active ? '（当前启用）' : ''),
                })),
                ...(creating ? [{ value: 'new', label: '新增配置（未保存）' }] : []),
              ]}
            />
            <Button disabled={busy} onClick={() => choose('new')}>
              新增配置
            </Button>
            <Button
              type="primary"
              disabled={busy || !profile || profile.active}
              onClick={() => void manage('activate')}
            >
              切换启用
            </Button>
            <Button danger disabled={busy || !profile} onClick={() => setDeleting(true)}>
              删除配置
            </Button>
          </div>
          {deleting && profile && (
            <div className={styles.deleteConfirmation}>
              <p>
                确认删除「{profile.name}」？
                {profile.active ? '当前 API 将停用，可再选择其他配置启用。' : ''}
                历史任务版本仍保留，删除不等于撤销供应商密钥。
              </p>
              <Button danger disabled={busy} onClick={() => void manage('delete')}>
                确认删除配置
              </Button>{' '}
              <Button disabled={busy} onClick={() => setDeleting(false)}>
                取消删除
              </Button>
            </div>
          )}
        </section>
      )}
      {!settings.data && !settings.error && <p role="status">正在读取模型配置…</p>}
      {initial && profiles.data && (
        <SettingsForm
          key={`${selection}:${formEpoch}`}
          initial={initial}
          profile={profile}
          creating={creating}
          disabled={managing}
          onBusy={setFormBusy}
          onDirty={() => {
            setDirty(true);
            setSelected(selection);
            setNotice(null);
          }}
          onSaved={async (result) => {
            setDirty(false);
            if ('id' in result) setSelected(result.id);
            await reload();
            if (!('id' in result)) setSelected(null);
            setNotice(
              'active' in result && !result.active
                ? '配置已保存，点击「切换启用」后用于新任务。'
                : '模型设置已保存并生效，可返回行情工作台选择模型进行分析。',
            );
          }}
        />
      )}
    </div>
  );
}
