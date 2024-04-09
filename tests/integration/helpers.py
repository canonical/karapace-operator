#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]

KAFKA = "kafka"
ZOOKEEPER = "zookeeper"
DATA_INTEGRATOR = "data-integrator"
TLS_CERTIFICATES_OPERATOR = "tls-certificates-operator"
