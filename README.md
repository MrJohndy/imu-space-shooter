
# IMU Space Shooter

I built this project to experiment with using an Arduino and gyroscope as a physical game controller. Instead of using a keyboard, I tilt the controller to move the spaceship.

The game is made with Python and Pygame and features asteroids, enemy aliens, power-ups, and boss battles.

## Features

- IMU-controlled spaceship movement
- Automatic shooting
- Multiple asteroid types
- Enemy aliens with different attacks
- Boss battles with unique abilities
- Power-ups and permanent upgrades
- Increasing difficulty
- Procedurally generated graphics

## Hardware

- Arduino UNO
- LSM6DSV IMU sensor
- USB serial connection

## Technologies

- Python
- Pygame
- PySerial
- Arduino IDE

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Upload the Arduino sketch from the `arduino` folder to your Arduino UNO.

Connect your Arduino to your computer and check the serial port configured in the Python file.

Run the game:

```bash
python imu_space_shooter.py
```

## Controls

- Tilt the controller to move.
- Shooting is automatic.
- Avoid asteroids and enemy attacks.
- Defeat bosses to unlock upgrades.

## Project Status

Currently developed as a personal robotics and programming project.

## Author

Johndy Q. Salomon
