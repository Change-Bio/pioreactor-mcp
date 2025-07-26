# -*- coding: utf-8 -*-
from __future__ import annotations

import click
from pioreactor.background_jobs.base import BackgroundJobWithDodgingContrib
from pioreactor.config import config
from pioreactor.hardware import PWM_TO_PIN
from pioreactor.utils.pwm import PWM
from pioreactor.whoami import get_latest_experiment_name
from pioreactor.whoami import get_unit_name


class Relay(BackgroundJobWithDodgingContrib):
    published_settings = {
        "is_relay_on": {"datatype": "boolean", "settable": True},
    }

    job_name = "relay"

    def __init__(self, unit: str, experiment: str, start_on: bool = True) -> None:
        super().__init__(unit=unit, experiment=experiment, plugin_name="relay")
        if start_on:
            self.duty_cycle = 100.0
            self.is_relay_on = True
        else:
            self.duty_cycle = 0.0
            self.is_relay_on = False

        self.pwm_pin = PWM_TO_PIN[config.get("PWM_reverse", "relay")]
        # looks at config.ini/configuration on UI to match
        # changed PWM channel 2 to "relay" on leader
        # whatevers connected to channel 2 will turn on/off

        self.pwm = PWM(
            self.pwm_pin, hz=10, unit=unit, experiment=experiment
        )  # since we also go 100% high or 0% low, we don't need hz, but some systems don't allow a very low hz (like hz=1).
        self.pwm.lock()

    def on_init_to_ready(self) -> None:
        super().on_init_to_ready()
        self.logger.debug(f"Starting relay {'ON' if self.is_relay_on else 'OFF'}.")
        self.pwm.start(self.duty_cycle)

    def set_is_relay_on(self, value: bool) -> None:
        if value == self.is_relay_on:
            return

        if value:
            self._set_duty_cycle(100)
            self.is_relay_on = True
        else:
            self._set_duty_cycle(0)
            self.is_relay_on = False

    def _set_duty_cycle(self, new_duty_cycle: float) -> None:
        self.duty_cycle = new_duty_cycle

        if hasattr(self, "pwm"):
            self.pwm.change_duty_cycle(self.duty_cycle)

    def on_ready_to_sleeping(self) -> None:
        super().on_ready_to_sleeping()
        self.set_is_relay_on(False)

    def on_sleeping_to_ready(self) -> None:
        super().on_sleeping_to_ready()
        self.set_is_relay_on(True)

    def on_disconnected(self) -> None:
        super().on_disconnected()
        self.set_is_relay_on(False)
        self.pwm.clean_up()

    def action_to_do_before_od_reading(self) -> None:
        self.set_is_relay_on(False)

    def action_to_do_after_od_reading(self) -> None:
        self.set_is_relay_on(True)


@click.command(name="relay")
@click.option(
    "-s",
    "--start-on",
    default=config.getint("relay.config", "start_on", fallback=1),
    type=click.BOOL,
)
def click_relay(start_on: bool) -> None:
    """
    Start the relay
    """
    job = Relay(
        unit=get_unit_name(),
        experiment=get_latest_experiment_name(),
        start_on=bool(start_on),
    )
    job.block_until_disconnected()


if __name__ == "__main__":
    click_relay()
