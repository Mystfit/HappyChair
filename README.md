# RPi 5 requirements

- In `/boot/firmware/config.txt` add the line `dtoverlay=pwm-2chan`
- Run the following.`echo 2 > /sys/class/pwm/pwmchip0/export`

# Run

- In repo folder run `source setup_env.sh`
- Start server with `python anim_webapp.py`
