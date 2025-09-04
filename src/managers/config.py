#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace config file management."""

import json

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import KAFKA_CONSUMER_GROUP, KAFKA_TOPIC, OTEL_GRPC_PORT, PORT, STATSD_PORT


class ConfigManager:
    """Object for handling Karapace config options."""

    def __init__(self, context: ClusterContext, workload: WorkloadBase) -> None:
        self.context = context
        self.workload = workload

    @property
    def parsed_confile(self) -> dict:
        """Return config file parsed as a dict."""
        raw_file = self.workload.read(self.workload.paths.karapace_config)
        if not raw_file:
            return {}

        return json.loads("\n".join(raw_file))

    @property
    def base_config(self) -> dict:
        """Return the Karapace config options."""
        if not self.context.kafka.relation:
            return {}

        replication_factor = min([3, len(self.context.kafka.relation.units)])
        return {
            # Active services
            "karapace_rest": False,
            "karapace_registry": True,
            # Replication properties
            "advertised_hostname": self.context.server.host,
            "advertised_protocol": "http",
            "advertised_port": None,
            "client_id": f"sr-{self.context.server.unit_id}",
            "master_eligibility": True,
            # REST server options
            "host": self.context.server.host,
            "port": PORT,
            "server_tls_certfile": None,  # running the server in HTTPS mode.
            "server_tls_keyfile": None,
            "access_logs_debug": False,
            "rest_authorization": False,
            "compatibility": "FULL",
            "log_level": "INFO",
            "protobuf_runtime_directory": "runtime",
            "session_timeout_ms": 10000,
            # Kafka connection settings
            "topic_name": KAFKA_TOPIC,
            "group_id": KAFKA_CONSUMER_GROUP,
            "replication_factor": replication_factor,
            "security_protocol": self.context.kafka.security_protocol,
            "ssl_cafile": self.workload.paths.ssl_cafile
            if self.context.cluster.tls_enabled
            else None,
            "ssl_certfile": self.workload.paths.ssl_certfile
            if self.context.cluster.tls_enabled
            else None,
            "ssl_keyfile": self.workload.paths.ssl_keyfile
            if self.context.cluster.tls_enabled
            else None,
            "bootstrap_uri": self.context.kafka.bootstrap_servers,
            "sasl_bootstrap_uri": self.context.kafka.bootstrap_servers,
            "sasl_mechanism": "SCRAM-SHA-512",
            "sasl_plain_username": self.context.kafka.username,
            "sasl_plain_password": self.context.kafka.password,
            # Auth options
            "registry_authfile": self.workload.paths.registry_authfile,
            "registry_ca": None,
            # Metrics options
            "statsd_host": self.context.server.host,
            "statsd_port": STATSD_PORT,
        }

    @property
    def otel_config(self) -> dict:
        """Return the OpenTelemetry config options."""
        if not self.context.kafka.relation:
            return {}

        return {
            "otel_endpoint_url": f"http://localhost:{OTEL_GRPC_PORT}",
            "otel_metrics_exporter": "OTLP",
            "otel_traces_exporter": "NOOP",
        }

    @property
    def config(self) -> dict:
        """Return all config options."""
        return self.base_config | self.otel_config

    def write_config_file(self) -> None:
        """Create the config file."""
        json_str = json.dumps(self.config, indent=2)
        self.workload.write(content=json_str, path=self.workload.paths.karapace_config)

    def set_environment(self) -> None:
        """Sets the env-vars for Karapace."""
        base_env = {f"KARAPACE_{k.upper()}": v for k, v in self.base_config.items()}
        otel_env = {f"KARAPACE_TELEMETRY__{k.upper()}": v for k, v in self.otel_config.items()}

        raw_current_env = self.workload.read("/etc/environment")
        current_env = self.workload.map_env(raw_current_env)

        env = current_env | base_env | otel_env
        content = "\n".join(
            [f"{key}={value if value is not None else ''}" for key, value in env.items()]
        )

        self.workload.write(content=content, path="/etc/environment")
