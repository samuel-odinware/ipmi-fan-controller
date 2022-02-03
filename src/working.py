#!/usr/bin/python3

import atexit
import re
from time import sleep, time
import subprocess
from typing import List, Optional, Pattern


class Sensor:
    def __init__(self, command: str, pattern: str) -> None:
        self.command = command
        self.pattern = pattern
        self.temps = []
        self.last_reset = time()

    def set_last_reset(self):
        self.last_reset = time()

    def fetch_temps(self) -> List[float]:
        process = subprocess.run(
            self.command, capture_output=True, shell=True, text=True
        )
        matches = re.findall(self.pattern, process.stdout)
        self.temps = [float(match) for match in matches]
        return self.temps

    def get_average_temp(self) -> float:
        """Calculates the average temparture.

        Returns:
            float: Average of input values
        """
        _divisor = 0
        _total = 0
        average = 0

        for temp in self.temps:
            if temp:
                _total += temp
                _divisor += 1

        if _divisor > 0:
            average = _total / _divisor

        return average

    def get_max_temp(self) -> float:
        if self.temps:
            return max(self.temps)
        return 0


class FanController:
    def __init__(self) -> None:
        self.static_speed_low: int = 0x02
        self.static_speed_high: int = 0x12
        self.default_threshold: int = 32
        self.base_temp: int = 30
        self.desired_temp_1: int = 40
        self.desired_temp_2: int = 45
        self.desired_temp_3: int = 55
        self.demand_1: int = 5
        self.demand_2: int = 40
        self.demand_3: int = 200
        self.hysteresis: int = 2
        self.current_mode: str = ""
        self.last_fan_setting: int = 0

    def set_fans_default(self):
        if self.current_mode != "default":
            print("::: Enable Dynamic Fan Control :::")
            for attempt in range(10):
                process = subprocess.run(
                    "ipmitool raw 0x30 0x30 0x01 0x01",
                    capture_output=True,
                    shell=True,
                    text=True,
                )
                if process.returncode == 0:
                    print("::: Enable Dynamic Fan Control Successful :::")
                    self.current_mode = "default"
                    self.last_fan_setting = 0
                    return True
                sleep(1)
                print("::: Retrying Dynamic Fan Control :::")
                print(f"Attempt: {attempt}")
            print("::: Retries of Dynamic Fan Control All Failed :::")
            return False
        return True

    def set_fans_servo(
        self,
        ambient_sensor: Sensor,
        cpu_sensor: Sensor,
        core_sensor: Sensor,
        hdd_sensor: Sensor,
    ):
        temps = [
            core_sensor.get_average_temp(),
            cpu_sensor.get_average_temp(),
            hdd_sensor.get_average_temp(),
        ]
        average_temp = sum(temps) / len(temps)
        weighted_average = max(average_temp, hdd_sensor.get_average_temp())

        print(f"Ambient temparture: {ambient_sensor.get_average_temp()}")
        print(f"Weighted average temparture: {weighted_average}")

        if not weighted_average or weighted_average == 0:
            print(
                "::: ERROR READING ALL TEMPARTURES! FALLING BACK TO IDRAC CONTROL :::"
            )
            self.set_fans_default()

        if self.current_mode != "set":
            print("::: Disable Dynamic Fan Control :::")
            process = subprocess.run(
                "ipmitool raw 0x30 0x30 0x01 0x00",
                capture_output=True,
                shell=True,
                text=True,
            )
            if process.returncode == 0:
                print("::: Disable Dynamic Fan Control Successful :::")
                self.current_mode = "set"
            else:
                print("::: Disable Dynamic Fan Control Failed :::")

        #   # FIXME: probably want to take into account ambient temperature - if
        #   # the difference between weighted_temp and ambient_temp is small
        #   # because ambient_temp is large, then less need to run the fans
        #   # because there's still low power demands
        demand = 0
        if weighted_average > self.base_temp and weighted_average < self.desired_temp_1:
            demand = 0 + (weighted_average - self.base_temp) * (self.demand_1 - 0) / (
                self.desired_temp_1 - self.base_temp
            )
        elif weighted_average >= self.desired_temp_2:
            demand = self.demand_2 + (weighted_average - self.desired_temp_2) * (
                self.demand_3 - self.demand_2
            ) / (self.desired_temp_3 - self.desired_temp_2)
        elif weighted_average >= self.desired_temp_1:
            demand = self.demand_1 + (weighted_average - self.desired_temp_1) * (
                self.demand_2 - self.demand_1
            ) / (self.desired_temp_2 - self.desired_temp_1)

        print(f"Demand: {demand:0.2f}")

        demand = int(
            self.static_speed_low
            + demand / 100 * (self.static_speed_high - self.static_speed_low)
        )
        if demand > 255:
            demand = 255

        print(f"Demand: {demand}")
        print(f"Fan setting: {self.last_fan_setting}")

        #   # ramp down the fans quickly upon lack of demand, don't ramp them up
        #   # to tiny spikes of 1 fan unit.  FIXME: But should implement long
        #   # term smoothing of +/- 1 fan unit
        if (
            not self.last_fan_setting
            or demand < self.last_fan_setting
            or demand > self.last_fan_setting + self.hysteresis
        ):
            print(f"::: ipmitool raw 0x30 0x30 0x02 0xff {demand:#x} :::")
            process = subprocess.run(
                f"ipmitool raw 0x30 0x30 0x02 0xff {demand:#x}",
                capture_output=True,
                shell=True,
                text=True,
            )
            if process.returncode == 0:
                print("::: Set Fan Speed Successful :::")
                self.current_mode = "set"
                self.last_fan_setting = demand
                return True
        print("No changes were made")
        return False


IPMI_INLET_SENSORNAME = "Inlet Temp"

ambient = Sensor(
    command="timeout -k 1 20 ipmitool sdr type temperature | awk '/Inlet Temp/'",
    pattern=r".*\| ([^ ]+) degrees C.*",
)
core = Sensor(
    command="timeout -k 1 20 sensors | awk '/Core/'",
    pattern=r".*:\s+\+([^ ]+).C.*",
)
cpu = Sensor(
    command="timeout -k 1 20 sensors | awk '/Package id/'",
    pattern=r".*:\s+\+([^ ]+).C.*",
)
hdd = Sensor(
    command="hddtemp /dev/sd? | awk '!/255/'",
    pattern=r"/dev/sd[a-z]:\s[a-zA-Z0-9-]*\s[a-zA-Z0-9-]*:\s([^ ]+).C",
)
fc = FanController()


@atexit.register
def end_application() -> None:
    print("::: Resetting Fans Back to Default :::")
    fc.set_fans_default()
    print("::: GOODBYE :::")


while True:
    if not ambient.temps:
        ambient.fetch_temps()
    if not hdd.temps:
        hdd.fetch_temps()

    core.fetch_temps()
    cpu.fetch_temps()

    print(f"Ambient Temparture: {ambient.temps}")
    print(f"Cores Temparture: {core.temps}")
    print(f"CPUs Temparture: {cpu.temps}")
    print(f"HDDs Temparture: {hdd.temps}")

    if ambient.get_average_temp() > fc.default_threshold:
        print(
            f"::: Falling back because of high ambient temparture; {ambient.get_average_temp()} > {fc.default_threshold}"
        )
        if not fc.set_fans_default():
            continue
    else:
        if not fc.set_fans_servo(
            ambient_sensor=ambient, cpu_sensor=cpu, core_sensor=core, hdd_sensor=hdd
        ):
            continue

    if (time() - ambient.last_reset) > 60:
        ambient.temps = []
        ambient.set_last_reset()
        fc.current_mode = "reset"

    if (time() - hdd.last_reset) > 1200:
        hdd.temps = []
        hdd.set_last_reset()

    sleep(3)
