#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for handling Karapace TLS configuration."""

import logging
import subprocess

from ops.pebble import ExecError

from core.cluster import ClusterContext
from core.workload import WorkloadBase

logger = logging.getLogger(__name__)


class TLSManager:
    """Manager for building necessary files for TLS auth."""

    def __init__(self, context: ClusterContext, workload: WorkloadBase):
        self.context = context
        self.workload = workload

    def generate_alias(self, app_name: str, relation_id: int) -> str:
        """Generate an alias from a relation. Used to identify ca certs."""
        return f"{app_name}-{relation_id}"

    def set_server_key(self) -> None:
        """Sets the unit private-key."""
        if not self.context.server.private_key:
            logger.error("Can't set private-key to unit, missing private-key in relation data")
            return

        self.workload.write(
            content=self.context.server.private_key, path=self.workload.paths.ssl_keyfile
        )

    def set_ca(self) -> None:
        """Set the Apache Kafka broker CA."""
        broker_ca = self.context.kafka.broker_ca

        # Compatibility: Kafka 3 charm sends `enabled` on `tls-ca` field.
        # We resort to using our CA in that case.
        # This only works if the broker & we use the same TLS provider.
        if not broker_ca or broker_ca == "enabled":
            broker_ca = self.context.server.ca

        if not broker_ca:
            logger.error("Can't set CA to unit, missing CA in relation data")
            return

        self.workload.write(content=broker_ca, path=self.workload.paths.ssl_cafile)

    def set_certificate(self) -> None:
        """Sets the unit certificate."""
        if not self.context.server.certificate:
            logger.error("Can't set certificate to unit, missing certificate in relation data")
            return

        self.workload.write(
            content=self.context.server.certificate, path=self.workload.paths.ssl_certfile
        )

    # FIXME: This method does not work since * is a bash thing.
    # We should either use `pathops` glob (which works on both substrates) or glob.glob.
    def remove_stores(self) -> None:
        """Cleans up all keys/certs/stores on a unit."""
        try:
            self.workload.exec(
                command="rm -rf *.pem *.key",
                working_dir=self.workload.paths.conf_path,
            )
        except (subprocess.CalledProcessError, ExecError) as e:
            logger.error(e.stdout)
            raise e
