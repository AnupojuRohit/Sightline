from models.task import Task


class HealthEngine:

    def calculate(self, tasks: list[Task]) -> int:

        score = 100

        for task in tasks:

            if not task.owner:
                score -= 15

            if task.blocked_by:
                score -= 10

            if task.status.lower() == "blocked":
                score -= 15

            if task.priority.lower() == "high":
                score -= 5

        return max(score, 0)