# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""Simple test for using adafruit_motorkit with a DC motor"""

import time

from adafruit_motorkit import MotorKit

kit = MotorKit()

# Forwards
kit.motor1.throttle = 1.0
time.sleep(1.0)

# Reverse
kit.motor1.throttle = -1.0
time.sleep(1.0)

# Stop
kit.motor1.throttle = 0
