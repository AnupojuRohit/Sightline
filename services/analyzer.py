from models.analysis import Analysis
from services.health_engine import HealthEngine
from services.risk_engine import RiskEngine


class Analyzer:

    def analyze(self, tasks):

        health_engine = HealthEngine()
        risk_engine = RiskEngine()

        score = health_engine.calculate(tasks)
        risks = risk_engine.analyze(tasks)

        overdue = sum(
            1
            for t in tasks
            if t.due_date and t.due_date.timestamp() < __import__("time").time()
        )

        blocked = sum(
            1
            for t in tasks
            if t.blocked_by
        )

        unassigned = sum(
            1
            for t in tasks
            if not t.owner
        )

        return Analysis(
            health_score=score,
            risks=risks,
            total_tasks=len(tasks),
            overdue_tasks=overdue,
            blocked_tasks=blocked,
            unassigned_tasks=unassigned,
        )