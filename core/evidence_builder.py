import logging

from core.github_checker import GitHubChecker
from core.rts_checker import RTSChecker
from models.mismatch import EvidenceBundle
from models.task import Task

logger = logging.getLogger(__name__)


class EvidenceBuilder:
    def __init__(self, github_checker: GitHubChecker, rts_checker: RTSChecker):
        self.github_checker = github_checker
        self.rts_checker = rts_checker

    def build(self, task: Task) -> EvidenceBundle:
        github = self.github_checker.check_task(task)
        rts = self.rts_checker.check_task(task)

        logger.info(
            "evidence_built",
            extra={
                "task_id": task.id,
                "github_count": len(github),
                "rts_count": len(rts),
            },
        )

        return EvidenceBundle(github=github, rts=rts)
