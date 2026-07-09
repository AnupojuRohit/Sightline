from datetime import datetime, timedelta

from models.task import Task


def load_mock_tasks():

    return [
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
        ),
    ]