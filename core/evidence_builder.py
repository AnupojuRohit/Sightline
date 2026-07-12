import logging

from core.github_checker import GitHubChecker
from core.rts_checker import RTSChecker
from models.mismatch import EvidenceBundle
from models.task import Task
from services.runtime_status import record_event

logger = logging.getLogger(__name__)


class EvidenceBuilder:
    def __init__(self, github_checker: GitHubChecker, rts_checker: RTSChecker):
        self.github_checker = github_checker
        self.rts_checker = rts_checker

    def build(self, task: Task, user_id: str | None = None) -> EvidenceBundle:
        logger.info("evidence_builder_entered task_id=%s user_id_present=%s", task.id, bool(user_id), extra={"task_id": task.id, "user_id_present": bool(user_id)})
        github = self.github_checker.check_task(task)
        rts = self.rts_checker.check_task(task, user_id=user_id)

        logger.info(
            "evidence_built task_id=%s github_count=%s rts_count=%s",
            task.id,
            len(github),
            len(rts),
            extra={
                "task_id": task.id,
                "github_count": len(github),
                "rts_count": len(rts),
            },
        )
        record_event("GitHub checked", f"{task.title}: {len(github)} result(s)", {"task_id": task.id})
        record_event("RTS checked", f"{task.title}: {len(rts)} result(s)", {"task_id": task.id})

        return EvidenceBundle(github=github, rts=rts)
