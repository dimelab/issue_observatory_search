"""Script to check Celery task status."""
from backend.celery_app import celery_app
from celery.result import AsyncResult


def check_recent_tasks():
    print("=" * 60)
    print("CELERY TASK STATUS CHECK")
    print("=" * 60)

    # Check if Celery is accessible
    try:
        inspector = celery_app.control.inspect()

        # Get active tasks
        print("\n--- ACTIVE TASKS ---")
        active = inspector.active()
        if active:
            for worker, tasks in active.items():
                print(f"\nWorker: {worker}")
                for task in tasks:
                    print(f"  Task: {task['name']}")
                    print(f"  ID: {task['id']}")
                    print(f"  Args: {task.get('args', [])}")
        else:
            print("No active tasks")

        # Get scheduled tasks
        print("\n--- SCHEDULED TASKS ---")
        scheduled = inspector.scheduled()
        if scheduled:
            for worker, tasks in scheduled.items():
                print(f"\nWorker: {worker}")
                for task in tasks:
                    print(f"  Task: {task['request']['name']}")
                    print(f"  ID: {task['request']['id']}")
        else:
            print("No scheduled tasks")

        # Get reserved tasks
        print("\n--- RESERVED TASKS ---")
        reserved = inspector.reserved()
        if reserved:
            for worker, tasks in reserved.items():
                print(f"\nWorker: {worker}")
                for task in tasks:
                    print(f"  Task: {task['name']}")
                    print(f"  ID: {task['id']}")
        else:
            print("No reserved tasks")

        # Get registered tasks
        print("\n--- REGISTERED TASKS ---")
        registered = inspector.registered()
        if registered:
            for worker, tasks in registered.items():
                print(f"\nWorker: {worker}")
                for task in sorted(tasks):
                    if 'network' in task.lower():
                        print(f"  ✓ {task}")
        else:
            print("No workers detected!")
            print("\nMake sure Celery workers are running:")
            print("  celery -A backend.celery_app worker -Q networks --loglevel=info")

        # Check stats
        print("\n--- WORKER STATS ---")
        stats = inspector.stats()
        if stats:
            for worker, info in stats.items():
                print(f"\nWorker: {worker}")
                print(f"  Total tasks: {info.get('total', {})}")
                print(f"  Pool: {info.get('pool', {})}")

    except Exception as e:
        print(f"\n✗ Error connecting to Celery: {e}")
        print("\nMake sure:")
        print("  1. Redis is running (redis-server)")
        print("  2. Celery worker is running:")
        print("     celery -A backend.celery_app worker -Q networks --loglevel=info")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    check_recent_tasks()
