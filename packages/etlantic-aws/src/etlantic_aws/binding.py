"""Pinned, secret-free ECS task binding and deterministic RunTask request."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from etlantic.control_plane import AcceptedExecutionReference

_ACCOUNT = re.compile(r"^[0-9]{12}$")
_REGION = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-[0-9]+$")
_REVISION_ARN = re.compile(
    r"^arn:(aws|aws-us-gov):ecs:([a-z0-9-]+):([0-9]{12}):task-definition/"
    r"[A-Za-z0-9_-]+:([1-9][0-9]*)$"
)
_IMAGE_DIGEST = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_MAX_REFERENCE_BYTES = 4096


def _required_text(name: str, value: object, *, max_length: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > max_length
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"{name} must contain 1 to {max_length} characters")
    return value


def _matches(pattern: str, value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _required_printable(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= 256
        and all(32 <= ord(char) < 127 for char in value)
    )


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a string array")
    result: list[str] = []
    for part in cast(Iterable[object], value):
        if not isinstance(part, str):
            raise ValueError(f"{name} must be a string array")
        result.append(part)
    return tuple(result)


def _as_mapping(value: object, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(message)
    return cast(Mapping[str, Any], value)


def _mapping_rows(value: object) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in cast(Iterable[object], value)
    ):
        return None
    return [cast(Mapping[str, Any], item) for item in cast(Iterable[object], value)]


@dataclass(frozen=True, slots=True)
class ECSExecutionBinding:
    """Immutable configuration for one Fargate task deployment."""

    account_id: str
    region: str
    cluster_arn: str
    task_definition_arn: str
    task_role_arn: str
    execution_role_arn: str
    container_name: str
    image_digest: str
    subnet_ids: tuple[str, ...]
    security_group_ids: tuple[str, ...]
    cpu: str
    memory: str
    platform_version: str = "1.4.0"
    assign_public_ip: bool = False
    operating_system_family: str = "LINUX"
    cpu_architecture: str = "X86_64"
    entry_point: tuple[str, ...] = ("etlantic-aws-ecs-worker",)

    def __post_init__(self) -> None:
        account_id: object = cast(object, self.account_id)
        if not _matches(_ACCOUNT.pattern, account_id):
            raise ValueError("account_id must be a 12 digit AWS account")
        region_value: object = cast(object, self.region)
        if not _matches(_REGION.pattern, region_value):
            raise ValueError("region must be an explicit AWS region")
        _required_text("cluster_arn", self.cluster_arn)
        match = _REVISION_ARN.fullmatch(self.task_definition_arn)
        if match is None:
            raise ValueError("task_definition_arn must pin a task-definition revision")
        partition, region, account_id, _ = match.groups()
        expected_partition = (
            "aws-us-gov" if self.region.startswith("us-gov-") else "aws"
        )
        if partition != expected_partition:
            raise ValueError("task definition partition does not match the region")
        if region != self.region or account_id != self.account_id:
            raise ValueError("task definition must match the configured account/region")
        if self.cluster_arn != (
            f"arn:{partition}:ecs:{self.region}:{self.account_id}:cluster/"
            + self.cluster_arn.rsplit("/", 1)[-1]
        ):
            raise ValueError("cluster_arn must match the configured account/region")
        for name, value in (
            ("task_role_arn", self.task_role_arn),
            ("execution_role_arn", self.execution_role_arn),
        ):
            _required_text(name, value)
            if not value.startswith(f"arn:{partition}:iam::{self.account_id}:role/"):
                raise ValueError(
                    f"{name} must be an IAM role in the configured account"
                )
        _required_text("container_name", self.container_name, max_length=255)
        if not _IMAGE_DIGEST.fullmatch(self.image_digest):
            raise ValueError("image_digest must include a pinned sha256 digest")
        if not self.subnet_ids or len(self.subnet_ids) > 16:
            raise ValueError("one to sixteen private subnet IDs are required")
        if not self.security_group_ids or len(self.security_group_ids) > 5:
            raise ValueError("one to five security group IDs are required")
        if len(set(self.subnet_ids)) != len(self.subnet_ids):
            raise ValueError("subnet_ids must not contain duplicates")
        if len(set(self.security_group_ids)) != len(self.security_group_ids):
            raise ValueError("security_group_ids must not contain duplicates")
        if any(
            not _matches(r"subnet-[0-9a-f]+", cast(object, item))
            for item in self.subnet_ids
        ):
            raise ValueError("subnet_ids must be explicit subnet identifiers")
        if any(
            not _matches(r"sg-[0-9a-f]+", cast(object, item))
            for item in self.security_group_ids
        ):
            raise ValueError("security_group_ids must be explicit security group IDs")
        cpu_value: object = cast(object, self.cpu)
        if not isinstance(cpu_value, str) or not cpu_value.isdigit():
            raise ValueError("cpu must be an explicit numeric Fargate value")
        memory_value: object = cast(object, self.memory)
        if not isinstance(memory_value, str) or not memory_value.isdigit():
            raise ValueError("memory must be an explicit numeric Fargate value")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.platform_version):
            raise ValueError("platform_version must be pinned, never LATEST")
        if type(self.assign_public_ip) is not bool:
            raise ValueError("assign_public_ip must be boolean")
        if self.assign_public_ip:
            raise ValueError("the qualified ECS binding requires private networking")
        if self.operating_system_family != "LINUX":
            raise ValueError("the initial ECS support matrix requires Linux")
        if self.cpu_architecture != "X86_64":
            raise ValueError("the initial ECS support matrix requires X86_64")
        if not self.entry_point or any(
            not _required_printable(item) for item in self.entry_point
        ):
            raise ValueError("entry_point must explicitly pin the installed worker")
        if self.entry_point != ("etlantic-aws-ecs-worker",):
            raise ValueError(
                "the initial ECS support matrix requires the ETLantic worker"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "region": self.region,
            "cluster_arn": self.cluster_arn,
            "task_definition_arn": self.task_definition_arn,
            "task_role_arn": self.task_role_arn,
            "execution_role_arn": self.execution_role_arn,
            "container_name": self.container_name,
            "image_digest": self.image_digest,
            "subnet_ids": list(self.subnet_ids),
            "security_group_ids": list(self.security_group_ids),
            "cpu": self.cpu,
            "memory": self.memory,
            "platform_version": self.platform_version,
            "assign_public_ip": self.assign_public_ip,
            "operating_system_family": self.operating_system_family,
            "cpu_architecture": self.cpu_architecture,
            "entry_point": list(self.entry_point),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ECSExecutionBinding:
        expected = {
            "account_id",
            "region",
            "cluster_arn",
            "task_definition_arn",
            "task_role_arn",
            "execution_role_arn",
            "container_name",
            "image_digest",
            "subnet_ids",
            "security_group_ids",
            "cpu",
            "memory",
            "platform_version",
            "assign_public_ip",
            "operating_system_family",
            "cpu_architecture",
            "entry_point",
        }
        if set(value) != expected:
            raise ValueError("ECS binding has unknown or missing fields")
        fields: dict[str, Any] = dict(value)
        for name in ("subnet_ids", "security_group_ids", "entry_point"):
            fields[name] = _string_tuple(fields[name], name)
        return cls(**fields)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def partition(self) -> str:
        match = _REVISION_ARN.fullmatch(self.task_definition_arn)
        assert match is not None
        return match.group(1)

    @property
    def execution_route(self) -> str:
        return f"ecs:{self.fingerprint}"

    def request(
        self, *, client_token: str, reference: AcceptedExecutionReference
    ) -> dict[str, Any]:
        token = _required_text("client_token", client_token, max_length=64)
        if not token.isascii() or any(
            ord(char) < 33 or ord(char) > 126 for char in token
        ):
            raise ValueError("client_token must be printable ASCII")
        reference_json = json.dumps(
            reference.to_dict(), separators=(",", ":"), sort_keys=True, allow_nan=False
        )
        if len(reference_json.encode("utf-8")) > _MAX_REFERENCE_BYTES:
            raise ValueError("accepted execution reference exceeds its size limit")
        return {
            "cluster": self.cluster_arn,
            "taskDefinition": self.task_definition_arn,
            "count": 1,
            "launchType": "FARGATE",
            "platformVersion": self.platform_version,
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": list(self.subnet_ids),
                    "securityGroups": list(self.security_group_ids),
                    "assignPublicIp": "ENABLED"
                    if self.assign_public_ip
                    else "DISABLED",
                }
            },
            "overrides": {
                "containerOverrides": [
                    {
                        "name": self.container_name,
                        "environment": [
                            {
                                "name": "ETLANTIC_ACCEPTED_REFERENCE_JSON",
                                "value": reference_json,
                            }
                        ],
                    }
                ]
            },
            "enableExecuteCommand": False,
            "clientToken": token,
            "startedBy": token[:36],
            "tags": [
                {"key": "etlantic:managed", "value": "true"},
                {"key": "etlantic:binding", "value": self.fingerprint[:32]},
            ],
        }

    def verify(self, ecs_client: Any, sts_client: Any) -> None:
        """Fail closed unless caller, cluster and pinned task definition match."""
        caller = _as_mapping(
            sts_client.get_caller_identity(), "AWS caller identity is unavailable"
        )
        if caller.get("Account") != self.account_id:
            raise RuntimeError("AWS caller account does not match the ECS binding")
        ecs_region = getattr(getattr(ecs_client, "meta", None), "region_name", None)
        if ecs_region is not None and ecs_region != self.region:
            raise RuntimeError("ECS client region does not match the binding")
        cluster_response = _as_mapping(
            ecs_client.describe_clusters(clusters=[self.cluster_arn]),
            "ECS cluster response is malformed",
        )
        clusters = _mapping_rows(cluster_response.get("clusters")) or []
        if (
            len(clusters) != 1
            or clusters[0].get("status") != "ACTIVE"
            or clusters[0].get("clusterArn") != self.cluster_arn
        ):
            raise RuntimeError("configured ECS cluster is unavailable or mismatched")
        response = _as_mapping(
            ecs_client.describe_task_definition(
                taskDefinition=self.task_definition_arn
            ),
            "ECS task-definition response is malformed",
        )
        task = _as_mapping(
            response.get("taskDefinition"), "ECS task definition is unavailable"
        )
        runtime_platform = _as_mapping(
            task.get("runtimePlatform") or {}, "ECS runtime platform is malformed"
        )
        all_containers = _mapping_rows(task.get("containerDefinitions"))
        if all_containers is None:
            raise RuntimeError("ECS container definitions are malformed")
        containers = [
            item for item in all_containers if item.get("name") == self.container_name
        ]
        if (
            task.get("taskDefinitionArn") != self.task_definition_arn
            or task.get("status") != "ACTIVE"
            or "FARGATE" not in task.get("requiresCompatibilities", [])
            or task.get("networkMode") != "awsvpc"
            or runtime_platform.get("operatingSystemFamily", "LINUX")
            != self.operating_system_family
            or runtime_platform.get("cpuArchitecture", "X86_64")
            != self.cpu_architecture
            or task.get("taskRoleArn") != self.task_role_arn
            or task.get("executionRoleArn") != self.execution_role_arn
            or str(task.get("cpu")) != self.cpu
            or str(task.get("memory")) != self.memory
            or len(containers) != 1
            or containers[0].get("image") != self.image_digest
            or containers[0].get("essential") is not True
            or containers[0].get("entryPoint") != list(self.entry_point)
            or containers[0].get("command", []) != []
        ):
            raise RuntimeError("pinned ECS task definition does not match its binding")


__all__ = ["ECSExecutionBinding"]
