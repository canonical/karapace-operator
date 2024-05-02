#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of globals common to the Karapace Charm."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, StatusBase, WaitingStatus

CHARM_KEY = "karapace"
SNAP_NAME = "charmed-karapace"
CHARMED_KARAPACE_SNAP_REVISION = 2
CONTAINER = "karapace"
PORT = 8081

PEER = "cluster"
KARAPACE_REL = "karapace"
KAFKA_REL = "kafka"
KAFKA_TOPIC = "_schemas"
KAFKA_CONSUMER_GROUP = "schema-registry"

ADMIN_USER = "operator"
INTERNAL_USERS = [ADMIN_USER]

SECRETS_APP = ["operator-password"]
SECRETS_UNIT = ["ca-cert", "csr", "certificate", "private-key"]

TLS_RELATION = "certificates"

# METRICS_RULES_DIR = "./src/alert_rules/prometheus"
# LOGS_RULES_DIR = "./src/alert_rules/loki"

SUBSTRATE = "vm"
USER = "snap_daemon"
GROUP = "snap_daemon"

PATHS = {
    "CONF": f"/var/snap/{SNAP_NAME}/current/etc/karapace",
    "LOGS": f"/var/snap/{SNAP_NAME}/common/var/log/karapace",
}


AuthMechanism = Literal["SASL_PLAINTEXT", "SASL_SSL", "SSL"]
DebugLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Substrate = Literal["vm", "k8s"]
DatabagScope = Literal["unit", "app"]


@dataclass
class StatusLevel:
    """Status object helper."""

    status: StatusBase
    log_level: DebugLevel


class Status(Enum):
    """Collection of possible statuses for the charm."""

    ACTIVE = StatusLevel(ActiveStatus(), "DEBUG")
    NO_PEER_RELATION = StatusLevel(MaintenanceStatus("no peer relation yet"), "DEBUG")
    SNAP_NOT_INSTALLED = StatusLevel(BlockedStatus(f"unable to install {SNAP_NAME} snap"), "ERROR")
    SERVICE_NOT_RUNNING = StatusLevel(BlockedStatus("karapace service not running"), "ERROR")
    KAFKA_NOT_RELATED = StatusLevel(BlockedStatus("missing required kafka relation"), "DEBUG")
    KAFKA_NOT_CONNECTED = StatusLevel(BlockedStatus("unit not connected to kafka"), "ERROR")
    KAFKA_TLS_MISMATCH = StatusLevel(
        BlockedStatus("tls must be enabled on both karapace and kafka"), "ERROR"
    )
    KAFKA_NO_DATA = StatusLevel(WaitingStatus("kafka credentials not created yet"), "DEBUG")
    NO_CREDS = StatusLevel(WaitingStatus("internal credentials not yet added"), "DEBUG")
    NO_CERT = StatusLevel(WaitingStatus("unit waiting for signed certificates"), "INFO")
