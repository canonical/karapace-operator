#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Karapace workload class and methods."""

import logging
import os
import subprocess

from charms.operator_libs_linux.v0 import apt, systemd

# from charms.operator_libs_linux.v1 import snap
from tenacity import retry
from tenacity.retry import retry_if_not_result
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from typing_extensions import override

from core.workload import WorkloadBase
from literals import GROUP, SERVICE_DEF, USER

logger = logging.getLogger(__name__)


class KarapaceWorkload(WorkloadBase):
    """Wrapper for performing common operations specific to the Karapace Snap."""

    SNAP_NAME = "charmed-karapace"
    SERVICE = "karapace"

    def __init__(self) -> None:
        pass

    @override
    def start(self) -> None:
        systemd.service_start(self.SERVICE)

    @override
    def stop(self) -> None:
        systemd.service_stop(self.SERVICE)

    @override
    def restart(self) -> None:
        systemd.service_restart(self.SERVICE)

    @override
    def read(self, path: str) -> list[str]:
        if not os.path.exists(path):
            return []
        else:
            with open(path) as f:
                content = f.read().split("\n")

        return content

    @override
    def write(self, content: str, path: str, mode: str = "w") -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode) as f:
            f.write(content)

        self.exec(f"chown -R {USER}:{GROUP} {path}")

    @override
    def exec(
        self, command: str, env: dict[str, str] | None = None, working_dir: str | None = None
    ) -> str:
        try:
            output = subprocess.check_output(
                command,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True,
                cwd=working_dir,
            )
            logger.debug(f"{output=}")
            return output
        except subprocess.CalledProcessError as e:
            logger.debug(f"cmd failed - cmd={e.cmd}, stdout={e.stdout}, stderr={e.stderr}")
            raise e

    @retry(
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        retry_error_callback=lambda state: state.outcome.result(),  # type: ignore
        retry=retry_if_not_result(lambda result: True if result else False),
    )
    @override
    def active(self) -> bool:
        return systemd.service_running(self.SERVICE)

    def install(self) -> bool:
        """Install karapace service.

        Returns:
            True if successfully installed. False otherwise.
        """
        apt.update()
        apt.add_package("python3-pip")

        try:
            self.exec("git clone https://github.com/Aiven-Open/karapace.git", working_dir="/root")
            self.exec(
                "pip3 install -r requirements/requirements.txt", working_dir="/root/karapace"
            )
            self.exec("python3 setup.py install", working_dir="/root/karapace")
        except subprocess.CalledProcessError:
            logger.error("Error on install")
            return False

        self.write(content=SERVICE_DEF, path="/etc/systemd/system/karapace.service")
        # self.write(content="", path="/root/authfile.json")

        return True
