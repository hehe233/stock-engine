import { Alert, Button } from 'antd';
import styles from './index.less';

export function ErrorNotice({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <Alert
      className={styles.root}
      type="error"
      showIcon
      title="请求未完成"
      description={error.message}
      action={
        retry ? (
          <Button size="small" aria-label="重试" onClick={retry}>
            重试
          </Button>
        ) : undefined
      }
    />
  );
}
