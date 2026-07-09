from datetime import datetime

from models.risk import Risk
from models.task import Task


class RiskEngine:

    def analyze(self, tasks: list[Task]) -> list[Risk]:

        risks = []

        today = datetime.now()

        for task in tasks:

            # No owner
            if not task.owner:
                risks.append(
                    Risk(
                        title=task.title,
                        severity="HIGH",
                        reason="Task has no owner.",
                        recommendation="Assign an owner."
                    )
                )

            # Overdue
            if task.due_date and task.due_date < today:

                risks.append(
                    Risk(
                        title=task.title,
                        severity="HIGH",
                        reason="Task is overdue.",
                        recommendation="Review deadline immediately."
                    )
                )

            # Blocked
            if task.blocked_by:

                risks.append(
                    Risk(
                        title=task.title,
                        severity="MEDIUM",
                        reason="Task is blocked.",
                        recommendation="Resolve dependency."
                    )
                )

        return risks