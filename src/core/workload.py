#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace workload."""

import secrets
import string
from abc import ABC, abstractmethod

from literals import PATHS


class KarapacePaths:
    """Object to store common paths for Karapace."""

    def __init__(self):
        self.conf_path = PATHS["CONF"]
        self.logs_path = PATHS["LOGS"]

    @property
    def karapace_config(self):
        """The main karapace.config.json filepath.

        Contains all the main configuration for the service.
        """
        return f"{self.conf_path}/karapace.config.json"

    @property
    def registry_authfile(self):
        """The main authfile filepath.

        Contains all the internal auth credentials for the service.
        """
        return f"{self.conf_path}/authfile.json"

    @property
    def ssl_cafile(self):
        """The CA file for Karapace - Kafka SSL."""
        return f"{self.conf_path}/cacert.pem"

    @property
    def ssl_certfile(self):
        """The certificate for Karapace - Kafka SSL."""
        return f"{self.conf_path}/cert.pem"

    @property
    def ssl_keyfile(self):
        """The private key for Karapace."""
        return f"{self.conf_path}/private.key"


class WorkloadBase(ABC):
    """Base interface for common workload operations."""

    paths = KarapacePaths()

    @abstractmethod
    def start(self) -> None:
        """Starts the workload service."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stops the workload service."""
        ...

    @abstractmethod
    def restart(self) -> None:
        """Restarts the workload service."""
        ...

    @abstractmethod
    def read(self, path: str) -> list[str]:
        """Reads a file from the workload.

        Args:
            path: the full filepath to read from

        Returns:
            List of string lines from the specified path
        """
        ...

    @abstractmethod
    def write(self, content: str, path: str, mode: str = "w") -> None:
        """Writes content to a workload file.

        Args:
            content: string of content to write
            path: the full filepath to write to
            mode: the write mode. Usually "w" for write, or "a" for append. Default "w"
        """
        ...

    @abstractmethod
    def exec(
        self, command: str, env: dict[str, str] | None = None, working_dir: str | None = None
    ) -> str:
        """Runs a command on the workload substrate."""
        ...

    @abstractmethod
    def active(self) -> bool:
        """Checks that the workload is active."""
        ...

    @abstractmethod
    def get_version(self) -> str:
        """Get the workload version.

        Returns:
            String of Karapace version
        """
        ...

    @abstractmethod
    def mkpasswd(self, username: str, password: str) -> str:
        """Return password string using Karapace helper CLI."""
        ...

    @staticmethod
    def generate_password() -> str:
        """Creates randomized string for use as app passwords.

        Returns:
            String of 32 randomized letter+digit characters
        """
        return "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(32)])
