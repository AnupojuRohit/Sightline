from datetime import datetime, timedelta

from models.task import Task
from services.analyzer import Analyzer
from services.gemini_service import GeminiService

def main():
    tasks = [
        Task(
            id="1",
            title="Backend API",
            owner=None,
            status="Todo",
            priority="High",
            due_date=datetime.now() - timedelta(days=2),
            blocked_by=[]
        ),
        Task(
            id="2",
            title="Frontend",
            owner="Alice",
            status="Blocked",
            priority="Medium",
            due_date=datetime.now() + timedelta(days=2),
            blocked_by=["1"]
        )
    ]

    analysis = Analyzer().analyze(tasks)
    report = GeminiService().analyze(analysis)

    print("\n")
    print("=" * 60)
    print("SIGHTLINE REPORT")
    print("=" * 60)
    print(report)


if __name__ == "__main__":
    main()
