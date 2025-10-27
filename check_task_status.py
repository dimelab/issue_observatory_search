"""Script to check Celery task status in Redis."""
import sys
from celery.result import AsyncResult
from backend.celery_app import celery_app


def check_task(task_id):
    """Check the status of a specific task."""
    print("=" * 60)
    print(f"TASK STATUS CHECK: {task_id}")
    print("=" * 60)

    result = AsyncResult(task_id, app=celery_app)

    print(f"\nTask ID: {task_id}")
    print(f"State: {result.state}")
    print(f"Ready: {result.ready()}")
    print(f"Successful: {result.successful()}")
    print(f"Failed: {result.failed()}")

    if result.info:
        print(f"\nInfo: {result.info}")

    if result.result:
        print(f"\nResult: {result.result}")

    if result.traceback:
        print(f"\nTraceback:\n{result.traceback}")

    # Check what queue it's in
    print("\n" + "-" * 60)
    print("Checking Redis queues...")
    print("-" * 60)

    from redis import Redis
    from backend.config import settings

    # Parse Redis URL
    redis_url = settings.celery_broker_url
    if redis_url.startswith('redis://'):
        host_port = redis_url.replace('redis://', '').split('/')[0]
        if ':' in host_port:
            host, port = host_port.split(':')
        else:
            host, port = host_port, 6379
    else:
        host, port = 'localhost', 6379

    redis_client = Redis(host=host, port=int(port), db=0, decode_responses=True)

    # Check all queues
    for queue_name in ['networks', 'scraping', 'analysis', 'celery']:
        queue_key = f"{queue_name}"
        length = redis_client.llen(queue_key)
        if length > 0:
            print(f"\nQueue '{queue_name}': {length} tasks")
            # Peek at tasks
            tasks = redis_client.lrange(queue_key, 0, 5)
            for i, task in enumerate(tasks[:3]):
                print(f"  Task {i+1}: {task[:100]}...")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_task_status.py <task_id>")
        print("\nExample:")
        print("  python check_task_status.py 9f98ac9a-0d03-42ac-9262-17cb4ecc4724")
        sys.exit(1)

    task_id = sys.argv[1]
    check_task(task_id)
