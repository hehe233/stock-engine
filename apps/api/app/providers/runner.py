import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from app.providers.base import ProviderError


def run_collector(asset_type: str, source: str, timeout: int, query: dict | None = None) -> dict:
    with TemporaryDirectory(prefix="stock-engine-") as temp:
        output = Path(temp) / "result.json"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.providers.collect",
                    "--asset-type",
                    asset_type,
                    "--source",
                    source,
                    "--output",
                    str(output),
                    *(["--query", json.dumps(query)] if query is not None else []),
                ],
                cwd=Path(__file__).resolve().parents[2],
                capture_output=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"{source} 采集超过 {timeout} 秒，已终止本次请求") from exc
        if result.returncode or not output.exists():
            raise ProviderError(f"{source} 采集进程异常退出")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if "error" in payload:
            raise ProviderError(f"{source} 公开接口暂不可用（{payload['error']}）")
        return payload
