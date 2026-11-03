from app.db import QuantRun
from app.quant.service import claim_experiment, fail_experiment
from app.runtime.processes import ChildProcess, process_event


class QuantSlot:
    """One experiment process; interrupted training is failed, never checkpoint-retried."""

    def __init__(self, sessions, settings, launch=ChildProcess.launch):
        self.sessions, self.settings, self.launch = sessions, settings, launch
        self.child, self.identifier = None, None

    def tick(self):
        if self.child is not None:
            with self.sessions() as session:
                row = session.get(QuantRun, self.identifier)
                cancelled = row.cancel_requested if row else False
            expired = self.child.expired(self.settings.quant_timeout_seconds)
            if cancelled or expired:
                code = self.child.stop()
                fail_experiment(
                    self.sessions,
                    self.identifier,
                    "实验已取消" if cancelled else "实验执行超时",
                    cancelled,
                )
                process_event(
                    "quant", self.identifier, "cancelled" if cancelled else "timeout", code
                )
                self.child, self.identifier = None, None
            elif (code := self.child.poll()) is not None:
                self.child.stop()
                fail_experiment(self.sessions, self.identifier, "实验进程中断")
                process_event("quant", self.identifier, "exited", code)
                self.child, self.identifier = None, None
        if self.child is None:
            self.identifier = claim_experiment(self.sessions, self.settings)
            if self.identifier:
                try:
                    self.child = self.launch("app.quant.run", self.identifier)
                except OSError:
                    fail_experiment(self.sessions, self.identifier, "实验进程启动失败")
                    process_event("quant", self.identifier, "spawn_failed")
                    self.identifier = None
                else:
                    process_event("quant", self.identifier, "started")

    def close(self):
        if self.child is not None:
            process_event("quant", self.identifier, "worker_shutdown", self.child.stop())
            self.child, self.identifier = None, None
