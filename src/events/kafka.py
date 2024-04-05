#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace-Kafka relation."""

import logging
from typing import TYPE_CHECKING

from charms.data_platform_libs.v0.data_interfaces import (
    BootstrapServerChangedEvent,
    KafkaRequires,
    TopicCreatedEvent,
    KafkaRequiresEventHandlers,
    KafkaRequiresData,
)
from ops import Object, RelationChangedEvent, RelationEvent, RelationBrokenEvent, EventBase
from ops.pebble import ExecError

from literals import INTERNAL_USERS, KAFKA_REL, Status

if TYPE_CHECKING:
    from charm import KarapaceCharm

logger = logging.getLogger(__name__)


class KafkaHandler(Object):
    """Implements the requirer-side logic for client applications relating to Kafka."""

    def __init__(self, charm) -> None:
        super().__init__(charm, "kafka_client")
        self.charm: "KarapaceCharm" = charm

        self.kafka_cluster = KafkaRequiresEventHandlers(
            self.charm, relation_data=self.charm.context.kafka_requirer_interface
        )

        self.framework.observe(
            self.charm.on[KAFKA_REL].relation_broken, self._on_kafka_broken
        )
        self.framework.observe(
            getattr(self.kafka_cluster.on, "bootstrap_server_changed"), self._on_kafka_bootstrap_server_changed
        )
        self.framework.observe(
            getattr(self.kafka_cluster.on, "topic_created"), self._on_kafka_topic_created
        )

    def _on_kafka_bootstrap_server_changed(self, event: BootstrapServerChangedEvent) -> None:
        """Handle the bootstrap server changed."""
        # Event triggered when a bootstrap server was changed for this application
        logger.info(f"Bootstrap servers changed into: {event.bootstrap_server}")
        self.charm._on_config_changed(event=event)
    
    def _on_kafka_topic_created(self, event: TopicCreatedEvent) -> None:
        """Handle the topic created event."""
        self.charm.config_manager.generate_config()
        self.charm.workload.start()

    def _on_kafka_broken(self, _: RelationBrokenEvent) -> None:
        """Handle the relation broken event."""
        logger.info(f"Stopping karapace process")
        self.charm.workload.stop()
