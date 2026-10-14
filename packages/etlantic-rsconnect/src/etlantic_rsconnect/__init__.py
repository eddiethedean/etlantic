"""Optional Posit Connect trigger integration for ETLantic."""

from etlantic_rsconnect.adapter import (
    CONNECT_SCHEDULE_API_PREVIEW,
    BindingStore,
    ConnectCapabilityReport,
    ConnectScheduleAdapter,
    ConnectScheduleBinding,
    ConnectScheduleDrift,
    ConnectScheduleGateway,
    PositSdkGateway,
    ScheduleOperationError,
    ScheduleOperationUnknown,
    inspect_connect_capabilities,
)
from etlantic_rsconnect.bundle import (
    TriggerBundle,
    build_trigger_bundle,
)
from etlantic_rsconnect.delivery import (
    DeliveryConfig,
    DeliveryError,
    DeliveryResult,
    HttpsTriggerDelivery,
    OccurrenceContext,
    build_trigger_envelope,
)
from etlantic_rsconnect.deployment import (
    DeploymentError,
    DeploymentIntent,
    DeploymentJournal,
    DeploymentOutcomeUnknown,
    DeploymentResult,
    RsconnectPythonDeployer,
)
from etlantic_rsconnect.limits import (
    MAX_DELIVERY_ATTEMPTS,
    MAX_DELIVERY_ELAPSED_SECONDS,
    MAX_REQUEST_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    MAX_RETRY_AFTER_SECONDS,
)

__version__ = "0.60.0"

__all__ = [
    "CONNECT_SCHEDULE_API_PREVIEW",
    "MAX_DELIVERY_ATTEMPTS",
    "MAX_DELIVERY_ELAPSED_SECONDS",
    "MAX_REQUEST_TIMEOUT_SECONDS",
    "MAX_RESPONSE_BYTES",
    "MAX_RETRY_AFTER_SECONDS",
    "BindingStore",
    "ConnectCapabilityReport",
    "ConnectScheduleAdapter",
    "ConnectScheduleBinding",
    "ConnectScheduleDrift",
    "ConnectScheduleGateway",
    "DeliveryConfig",
    "DeliveryError",
    "DeliveryResult",
    "DeploymentError",
    "DeploymentIntent",
    "DeploymentJournal",
    "DeploymentOutcomeUnknown",
    "DeploymentResult",
    "HttpsTriggerDelivery",
    "OccurrenceContext",
    "PositSdkGateway",
    "RsconnectPythonDeployer",
    "ScheduleOperationError",
    "ScheduleOperationUnknown",
    "TriggerBundle",
    "__version__",
    "build_trigger_bundle",
    "build_trigger_envelope",
    "inspect_connect_capabilities",
]
