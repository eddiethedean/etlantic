"""Optional AWS Scheduler and ECS integrations for ETLantic."""

from etlantic_aws.binding import ECSExecutionBinding
from etlantic_aws.dispatcher import ECSDispatchResult, ECSDispatcher
from etlantic_aws.relay import (
    RelayRetryRequired,
    ScheduledTriggerRelay,
    lambda_handler,
    load_trusted_relay,
)
from etlantic_aws.scheduler import EventBridgeScheduler, schedule_name
from etlantic_aws.worker import ECSWorker, read_task_metadata

__version__ = "0.61.0"

__all__ = [
    "ECSDispatchResult",
    "ECSDispatcher",
    "ECSExecutionBinding",
    "ECSWorker",
    "EventBridgeScheduler",
    "RelayRetryRequired",
    "ScheduledTriggerRelay",
    "__version__",
    "lambda_handler",
    "load_trusted_relay",
    "read_task_metadata",
    "schedule_name",
]
