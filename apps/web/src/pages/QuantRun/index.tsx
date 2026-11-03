import { useParams } from 'react-router-dom';
import { QuantRunReport } from '../../features/quant/QuantRunReport';
import styles from './index.less';

export function QuantRunPage() {
  const { id = '' } = useParams();
  return (
    <div className={styles.root}>
      <QuantRunReport id={id} />
    </div>
  );
}
