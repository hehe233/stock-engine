"""Fixed artifact paths, integrity checks and owned writes; no client-provided SQL."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import duckdb
from fastapi import HTTPException

FILENAMES = {"bars.parquet", "predictions.parquet", "models.json"}


def artifact_path(settings, mode, identifier, filename):
    UUID(identifier)
    if mode not in {"public", "demo"} or filename not in FILENAMES:
        raise ValueError("无效实验文件")
    return Path(settings.quant_artifact_dir).resolve() / mode / identifier / filename


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_frame(settings, row):
    path = artifact_path(settings, row.mode, row.id, "bars.parquet")
    if not path.is_file() or checksum(path) != row.checksum:
        raise ValueError("数据文件缺失或哈希不匹配，请重新导入；拒绝使用变更后的数据")
    with duckdb.connect(config={"threads": 1}) as db:
        return (
            db.execute("SELECT * FROM read_parquet(?) ORDER BY symbol, date", [str(path)])
            .to_arrow_table()
            .to_pandas()
        )


def checked_artifact(settings, row, filename):
    if row.mode != settings.market_provider:
        raise HTTPException(404, "实验不存在")
    if filename not in {"predictions.parquet", "models.json"}:
        raise ValueError("无效实验文件")
    if row.status != "succeeded":
        raise HTTPException(409, "实验尚未成功完成")
    path = artifact_path(settings, row.mode, row.id, filename)
    expected = row.result.get("artifacts", {}).get(filename)
    if not path.is_file() or not expected or checksum(path) != expected:
        raise HTTPException(409, "实验产物缺失或已变化，拒绝读取")
    return path


def prediction_page(settings, row, page):
    if page < 1:
        raise ValueError("页码必须大于零")
    path = checked_artifact(settings, row, "predictions.parquet")
    with duckdb.connect(config={"threads": 1}) as db:
        count = db.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
        frame = (
            db.execute(
                "SELECT * FROM read_parquet(?) ORDER BY date DESC, symbol LIMIT 50 OFFSET ?",
                [str(path), (page - 1) * 50],
            )
            .to_arrow_table()
            .to_pandas()
        )
    return {"total": count, "items": frame.to_dict("records")}


class ArtifactWrite:
    """Own one new version directory. Preserve it only once metadata is committed.

    Existing directories are never overwritten or cleaned. On an ambiguous DB commit,
    callers preserve files until they can establish that no durable reference exists.
    """

    def __init__(self, settings, mode, identifier):
        self.settings, self.mode, self.identifier = settings, mode, identifier
        self.directory = artifact_path(settings, mode, identifier, "bars.parquet").parent
        self.preserved = False
        self.paths = []

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=False)
        return self

    def _write(self, filename, write):
        path = artifact_path(self.settings, self.mode, self.identifier, filename)
        temp = path.with_suffix(".tmp")
        self.paths.extend([temp, path])
        write(temp)
        temp.replace(path)
        return checksum(path)

    def frame(self, filename, frame):
        return self._write(filename, lambda path: frame.to_parquet(path, index=False))

    def models(self, models):
        return self._write(
            "models.json",
            lambda path: path.write_text(
                json.dumps(models, ensure_ascii=False, allow_nan=False), encoding="utf-8"
            ),
        )

    def preserve(self):
        self.preserved = True

    def discard(self):
        self.preserved = False

    def __exit__(self, exc_type, exc, traceback):
        if not self.preserved:
            for path in self.paths:
                path.unlink(missing_ok=True)
            self.directory.rmdir()
