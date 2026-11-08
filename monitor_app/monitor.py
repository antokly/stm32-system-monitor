"""
monitoring dashboard for STM32L476RG

    pip install pyserial
    python monitor.py COMX ping (Windows)
    python monitor.py /dev/ttyACM1 ping (Linux)
    python stm32_driver.py COMX temp | vbat | adc | all
    python stm32_driver.py COMX pwm 1 45
"""

from ui.monitor_cli import main_cli
from ui.monitor_gui import main_gui

MODE_CLI = True

if __name__ == "__main__":
    if MODE_CLI == True:
        main_cli()
    else:
        main_gui()

