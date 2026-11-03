from app.db import ResearchJob
from app.jobs.service import claim_job, finish_failed
from app.runtime.processes import ChildProcess, process_event


class AgentSlot:
    """One leased Agent process; interrupted work keeps its checkpoint for recovery."""

    def __init__(self, sessions, settings, launch=ChildProcess.launch):
        self.sessions, self.settings, self.launch = sessions, settings, launch
        self.child, self.active = None, None

    def tick(self):
        if self.child is not None:
            identifier, owner = self.active
            with self.sessions() as session:
                job = session.get(ResearchJob, identifier)
                owned = job is not None and job.lease_owner == owner
                cancelled = job.cancel_requested if job else False
            expired = self.child.expired(self.settings.job_timeout_seconds)
            if not owned:
                code = self.child.stop()
                process_event("agent", identifier, "lease_lost", code)
                self.child, self.active = None, None
            elif cancelled or expired:
                code = self.child.stop()
                finish_failed(
                    self.sessions,
                    identifier,
                    owner,
                    "任务已取消" if cancelled else "任务执行超时",
                    cancelled,
                )
                process_event("agent", identifier, "cancelled" if cancelled else "timeout", code)
                self.child, self.active = None, None
            elif (code := self.child.poll()) is not None:
                self.child.stop()
                finish_failed(self.sessions, identifier, owner, "执行进程中断，检查点已保留")
                process_event("agent", identifier, "exited", code)
                self.child, self.active = None, None
        if self.child is None:
            self.active = claim_job(self.sessions, self.settings)
            if self.active:
                identifier, owner = self.active
                try:
                    self.child = self.launch("app.agents.run_job", identifier, owner)
                except OSError:
                    finish_failed(
                        self.sessions, identifier, owner, "执行进程启动失败，检查点已保留"
                    )
                    process_event("agent", identifier, "spawn_failed")
                    self.active = None
                else:
                    process_event("agent", identifier, "started")

    def close(self):
        if self.child is not None:
            process_event("agent", self.active[0], "worker_shutdown", self.child.stop())
            self.child, self.active = None, None
