#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace-Kafka relation."""

import logging
from typing import TYPE_CHECKING

from charms.data_platform_libs.v0.data_interfaces import (
    BootstrapServerChangedEvent,
    KafkaRequirerEventHandlers,
    TopicCreatedEvent,
)
from ops import Object, RelationBrokenEvent

from literals import KAFKA_REL, Status

if TYPE_CHECKING:
    from charm import KarapaceCharm

logger = logging.getLogger(__name__)


class KafkaHandler(Object):
    """Implements the requirer-side logic for client applications relating to Kafka."""

    def __init__(self, charm) -> None:
        super().__init__(charm, "kafka_client")
        self.charm: "KarapaceCharm" = charm

        self.kafka = KafkaRequirerEventHandlers(
            self.charm, relation_data=self.charm.context.kafka_requirer_interface
        )

        self.framework.observe(self.charm.on[KAFKA_REL].relation_broken, self._on_kafka_broken)
        self.framework.observe(
            getattr(self.kafka.on, "bootstrap_server_changed"),
            self._on_kafka_bootstrap_server_changed,
        )
        self.framework.observe(
            getattr(self.kafka.on, "topic_created"), self._on_kafka_topic_created
        )

    def _on_kafka_bootstrap_server_changed(self, event: BootstrapServerChangedEvent) -> None:
        """Handle the bootstrap server changed."""
        # Event triggered when a bootstrap server was changed for this application
        logger.info(f"Bootstrap servers changed into: {event.bootstrap_server}")
        self.charm.on.config_changed.emit()

    def _on_kafka_topic_created(self, _: TopicCreatedEvent) -> None:
        """Handle the topic created event."""
        self.charm.config_manager.generate_config()
        self.charm.workload.start()

        # Checks to ensure charm status gets set and there are no config options missing
        self.charm.on.config_changed.emit()

    def _on_kafka_broken(self, _: RelationBrokenEvent) -> None:
        """Handle the relation broken event."""
        logger.info("Stopping karapace process")
        self.charm.workload.stop()
        self.charm._set_status(Status.KAFKA_NOT_RELATED)
