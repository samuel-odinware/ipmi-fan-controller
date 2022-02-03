#!/usr/bin/python3

import atexit
import re
import subprocess
import time
from typing import List

import log

_DEGREE_SIGN = "\N{DEGREE SIGN}"
DEGREE_SYMBOL = f"{_DEGREE_SIGN}C"

IPMI_INLET_SENSORNAME = "Inlet Temp"


class Sensor:
    def __init__(self, command: str, pattern: str) -> None:
        self.command = command
        self.pattern = pattern
        self.temps: List[float] = []
        self.last_sensor_reading = time.time()

    def set_last_sensor_reading(self) -> None:
        """Update time of last sensor reading."""
        self.last_sensor_reading = time.time()

    def clear_temps(self) -> None:
        """Clear stored tempartures."""
        self.temps = []

    def fetch_temps(self) -> List[float]:
        """Get sensor data and parse results.

        Returns:
            List[float]: Parsed tempatures
        """
        process = subprocess.run(
            self.command, capture_output=True, shell=True, text=True
        )
        matches = re.findall(self.pattern, process.stdout)
        self.temps = [float(match) for match in matches]
        self.set_last_sensor_reading()
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
        """Get max temparture for a given sensor.

        Returns:
            float: Max temparture in degress celcius
        """
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
            log.info("::: Enable Dynamic Fan Control :::")
            for attempt in range(10):
                process = subprocess.run(
                    "ipmitool raw 0x30 0x30 0x01 0x01",
                    capture_output=True,
                    shell=True,
                    text=True,
                )
                if process.returncode == 0:
                    log.info("::: Enable Dynamic Fan Control Successful :::")
                    self.current_mode = "default"
                    self.last_fan_setting = 0
                    return True
                time.sleep(1)
                log.warning("::: Retrying Dynamic Fan Control :::")
                log.warning(f"Attempt: {attempt}")
            log.error("::: Retries of Dynamic Fan Control All Failed :::")
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

        log.info(
            f"Ambient temparture: {ambient_sensor.get_average_temp()}{DEGREE_SYMBOL}"
        )
        log.info(f"Weighted average temparture: {weighted_average}{DEGREE_SYMBOL}")

        if not weighted_average or weighted_average == 0:
            log.error(
                "::: ERROR READING ALL TEMPARTURES! FALLING BACK TO IDRAC CONTROL :::"
            )
            self.set_fans_default()

        if self.current_mode != "set":
            log.info("::: Disable Dynamic Fan Control :::")
            process = subprocess.run(
                "ipmitool raw 0x30 0x30 0x01 0x00",
                capture_output=True,
                shell=True,
                text=True,
            )
            if process.returncode == 0:
                log.info("::: Disable Dynamic Fan Control Successful :::")
                self.current_mode = "set"
            else:
                log.error("::: Disable Dynamic Fan Control Failed :::")

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

        demand = int(
            self.static_speed_low
            + demand / 100 * (self.static_speed_high - self.static_speed_low)
        )
        if demand > 255:
            demand = 255

        log.info(f"Demand: {demand}")
        log.info(f"Fan setting: {self.last_fan_setting}")

        #   # ramp down the fans quickly upon lack of demand, don't ramp them up
        #   # to tiny spikes of 1 fan unit.  FIXME: But should implement long
        #   # term smoothing of +/- 1 fan unit
        if (
            not self.last_fan_setting
            or demand < self.last_fan_setting
            or demand > self.last_fan_setting + self.hysteresis
        ):
            log.info(f"::: ipmitool raw 0x30 0x30 0x02 0xff {demand:#x} :::")
            process = subprocess.run(
                f"ipmitool raw 0x30 0x30 0x02 0xff {demand:#x}",
                capture_output=True,
                shell=True,
                text=True,
            )
            if process.returncode == 0:
                log.info("::: Set Fan Speed Successful :::")
                self.current_mode = "set"
                self.last_fan_setting = demand
                return True
        log.info("No changes were made")
        return False


def main() -> None:
    """Main service loop."""
    while True:
        if not ambient.temps:
            ambient.fetch_temps()
        if not hdd.temps:
            hdd.fetch_temps()

        core.fetch_temps()
        cpu.fetch_temps()

        log.info(f"Ambient Temparture: {ambient.temps}")
        log.info(f"Cores Temparture: {core.temps}")
        log.info(f"CPUs Temparture: {cpu.temps}")
        log.info(f"HDDs Temparture: {hdd.temps}")

        if ambient.get_average_temp() > fc.default_threshold:
            log.info(
                f"::: Falling back because of high ambient temparture; {ambient.get_average_temp()} > {fc.default_threshold}"
            )
            if not fc.set_fans_default():
                continue
        else:
            if not fc.set_fans_servo(
                ambient_sensor=ambient, cpu_sensor=cpu, core_sensor=core, hdd_sensor=hdd
            ):
                continue

        if (time.time() - ambient.last_sensor_reading) > 60:
            ambient.temps = []
            ambient.set_last_sensor_reading()
            fc.current_mode = "reset"

        if (time.time() - hdd.last_sensor_reading) > 1200:
            hdd.temps = []
            hdd.set_last_sensor_reading()

        time.sleep(3)


@atexit.register
def end_application() -> None:
    log.info("::: Resetting Fans Back to Default :::")
    fc.set_fans_default()
    log.info("::: GOODBYE :::")


if __name__ == "__main__":
    log.init()
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
    main()
