#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace config file management."""

import json

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import KAFKA_CONSUMER_GROUP, KAFKA_TOPIC, PORT


class ConfigManager:
    """Object for handling Karapace config options."""

    def __init__(self, context: ClusterContext, workload: WorkloadBase) -> None:
        self.context = context
        self.workload = workload

        # FIXME remove after kafka_client
        self.username = ""
        self.password = ""
        self.uris = ""

    @property
    def parsed_confile(self) -> dict:
        """Return authfile parsed as a dict."""
        return json.loads("\n".join(self.workload.read(self.workload.paths.karapace_config)))

    @property
    def config(self) -> dict:
        """Return the config options."""
        return {
            "advertised_hostname": self.context.server.host,
            "access_logs_debug": False,
            "rest_authorization": False,
            "client_id": "sr-1",
            "compatibility": "FULL",
            "group_id": KAFKA_CONSUMER_GROUP,
            "host": self.context.server.host,
            "log_level": "INFO",
            "port": PORT,
            "master_eligibility": True,
            "replication_factor": 1,  # FIXME dynamic depending on related units?
            "karapace_rest": False,
            "karapace_registry": True,
            "topic_name": KAFKA_TOPIC,
            "protobuf_runtime_directory": "runtime",
            "session_timeout_ms": 10000,
            "security_protocol": "SASL_SSL"
            if self.context.cluster.tls_enabled
            else "SASL_PLAINTEXT",
            "ssl_cafile": self.workload.paths.ssl_cafile
            if self.context.cluster.tls_enabled
            else None,
            "ssl_certfile": self.workload.paths.ssl_certfile
            if self.context.cluster.tls_enabled
            else None,
            "ssl_keyfile": self.workload.paths.ssl_keyfile
            if self.context.cluster.tls_enabled
            else None,
            "bootstrap_uri": self.uris,  # FIXME self.context.kafka.bootstrap_servers
            "sasl_bootstrap_uri": self.uris,  # FIXME self.context.kafka.bootstrap_servers
            "sasl_mechanism": "SCRAM-SHA-512",
            "sasl_plain_username": self.username,  # FIXME self.context.kafka.username
            "sasl_plain_password": self.password,  # FIXME self.context.kafka.password
            "registry_authfile": self.workload.paths.registry_authfile,
            "server_tls_certfile": None,  # Following options are for running the server in HTTPS mode.
            "server_tls_keyfile": None,
            "registry_ca": None,
        }

    # FIXME: temporary until kafka_client is enabled
    def _update_config(self, uris: str, username: str, password: str) -> None:
        """Update internal config options."""
        self.uris = uris
        self.username = username
        self.password = password

    def generate_config(self) -> None:
        """Create the config file."""
        json_str = json.dumps(self.config, indent=2)
        self.workload.write(content=json_str, path=self.workload.paths.karapace_config)
