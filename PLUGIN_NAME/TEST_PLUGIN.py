# -*- coding: utf-8 -*-


# Put testing code in here, for example:

```
from __future__ import annotations

from time import sleep

from pioreactor.pubsub import publish

from .relay import Relay


def test_relay_init_start_on():
    with Relay("unit", "test_relay_init_start_on", start_on=True) as r:
        assert r.duty_cycle == 100
        assert r.is_relay_on is True


def test_relay_init_start_off():
    with Relay("unit", "test_relay_init_start_off", start_on=False) as r:
        assert r.duty_cycle == 0
        assert r.is_relay_on is False


def test_set_is_relay_on_true_to_false():
    with Relay("unit", "test_set_is_relay_on_true_to_false", start_on=True) as r:
        r.set_is_relay_on(False)
        assert r.duty_cycle == 0
        assert r.is_relay_on is False


def test_set_is_relay_on_false_to_true_to_false():
    with Relay("unit", "test_set_is_relay_on_false_to_true_to_false", start_on=False) as r:
        r.set_is_relay_on(True)
        assert r.duty_cycle == 100
        assert r.is_relay_on is True

        publish(f"pioreactor/{r.unit}/{r.experiment}/relay/is_relay_on/set", False)
        sleep(0.5)
        assert r.duty_cycle == 0
        assert r.is_relay_on is False


def test_on_ready_to_sleeping():
    with Relay("unit", "test_on_ready_to_sleeping", start_on=True) as r:
        r.on_ready_to_sleeping()
        assert r.is_relay_on is False


def test_on_sleeping_to_ready():
    with Relay("unit", "test_on_sleeping_to_ready", start_on=True) as r:
        r.on_sleeping_to_ready()
        assert r.is_relay_on is True


def test_action_to_do_before_od_reading():
    with Relay("unit", "test_action_to_do_before_od_reading", start_on=True) as r:
        r.action_to_do_before_od_reading()
        assert r.is_relay_on is False


def test_action_to_do_after_od_reading():
    with Relay("unit", "test_action_to_do_after_od_reading", start_on=True) as r:
        r.action_to_do_after_od_reading()
        assert r.is_relay_on is True
```
