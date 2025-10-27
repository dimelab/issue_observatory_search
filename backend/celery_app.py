"""Celery application configuration for background tasks."""
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from backend.config import settings

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "issue_observatory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "backend.tasks.scraping_tasks",
        "backend.tasks.analysis_tasks",
        "backend.tasks.network_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Task routing (separate queues for different task types)
    task_routes={
        "backend.tasks.scraping_tasks.*": {"queue": "scraping"},
        "backend.tasks.analysis_tasks.*": {"queue": "analysis"},
        "backend.tasks.network_tasks.*": {"queue": "networks"},
        "backend.tasks.advanced_search_tasks.*": {"queue": "search"},
    },

    # Queue priorities (1 = lowest, 10 = highest)
    task_queue_max_priority=10,
    task_default_priority=5,

    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit

    # Task result settings
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Worker settings (optimized for performance)
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
    worker_disable_rate_limits=False,
    worker_pool_restarts=True,  # Restart worker pool on failures

    # Task acknowledgment
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Beat scheduler (for periodic tasks)
    beat_schedule={
        # Example: cleanup old jobs every day
        # "cleanup-old-jobs": {
        #     "task": "backend.tasks.scraping_tasks.cleanup_old_jobs",
        #     "schedule": crontab(hour=2, minute=0),
        # },
    },

    # Monitoring
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_track_started=True,
)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """
    Signal handler called before task execution.

    Args:
        sender: Task class
        task_id: Task ID
        task: Task instance
        args: Task positional arguments
        kwargs: Task keyword arguments
    """
    logger.info(f"Task {task.name} (ID: {task_id}) starting with args={args}, kwargs={kwargs}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    """
    Signal handler called after task execution.

    Args:
        sender: Task class
        task_id: Task ID
        task: Task instance
        args: Task positional arguments
        kwargs: Task keyword arguments
        retval: Task return value
        state: Task state (SUCCESS, FAILURE, etc.)
    """
    logger.info(f"Task {task.name} (ID: {task_id}) finished with state={state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra):
    """
    Signal handler called when task fails.

    Args:
        sender: Task class
        task_id: Task ID
        exception: Exception raised
        args: Task positional arguments
        kwargs: Task keyword arguments
        traceback: Traceback string
        einfo: Exception info
    """
    logger.error(
        f"Task {sender.name} (ID: {task_id}) failed with exception: {exception}\n"
        f"Args: {args}\n"
        f"Kwargs: {kwargs}\n"
        f"Traceback: {traceback}"
    )


# Auto-discover tasks
celery_app.autodiscover_tasks([
    "backend.tasks",
])


if __name__ == "__main__":
    celery_app.start()
