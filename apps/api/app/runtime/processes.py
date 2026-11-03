"""Only process mechanics; task state and recovery belong to their execution slots."""

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def process_event(kind, identifier, outcome, exit_code=None):
    # Do not log arguments, credentials, model output or portfolio data.
    logger.info(
        json.dumps(
            {
                "event": "worker_process",
                "kind": kind,
                "task_id": identifier,
                "outcome": outcome,
                "exit_code": exit_code,
            }
        )
    )


@dataclass
class ChildProcess:
    process: subprocess.Popen
    started: float

    @classmethod
    def launch(cls, module, *args):
        process = subprocess.Popen(
            [sys.executable, "-m", module, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return cls(process, time.monotonic())

    def expired(self, timeout):
        return time.monotonic() - self.started > timeout

    def poll(self):
        return self.process.poll()

    def stop(self):
        if self.process.poll() is None:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass  # Child exited between poll and kill; still reap it.
        return self.process.wait()
