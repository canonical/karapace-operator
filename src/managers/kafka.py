#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Kafka utils and management."""

from charms.kafka.v0.client import KafkaClient

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import KAFKA_TOPIC


class KafkaManager:
    """Object for handling Kafka."""

    def __init__(self, context: ClusterContext, workload: WorkloadBase) -> None:
        self.context = context
        self.workload = workload

    def brokers_active(self) -> bool:
        """Check that Kafka is active."""
        # FIXME If SSL connection is enabled we need SSL paths added to this KafkaClient
        client = KafkaClient(
            servers=self.context.kafka.bootstrap_servers.split(","),
            username=self.context.kafka.username,
            password=self.context.kafka.password,
            security_protocol=self.context.kafka.security_protocol,
            cafile_path=self.workload.paths.ssl_cafile,
            certfile_path=self.workload.paths.ssl_certfile,
            keyfile_path=self.workload.paths.ssl_keyfile,
        )
        try:
            client.describe_topics([KAFKA_TOPIC])
        except Exception:
            return False
        return True
