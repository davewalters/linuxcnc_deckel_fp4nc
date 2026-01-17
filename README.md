# Deckel FP4NC LinuxCNC Retrofit

This repository contains configuration files and custom Python components for a LinuxCNC retrofit of a 1985 Deckel FP4NC CNC milling machine.

The custom components include:
- Gearbox control logic
- Spindle and central lubrication control
- A mimic panel for monitoring the gearshift process within the `qtdragon_hd` user interface

The machine retains the original OEM servo motors and axis linear encoders, but has been retrofitted with a new electrical cabinet incorporating:
- Parker 514C servo drives
- A VFD for spindle motor control
- Safety relays for monitoring the E-stop chains
- A new machine control panel

A set of wiring diagrams is also included for reference.

## Safety Notice

These configuration files, custom components, and wiring diagrams are shared for reference and educational purposes only.

CNC machines and motion-control systems can cause damage or injury if configured or operated incorrectly. It is the responsibility of the user to review, test, and validate any configuration for their specific machine, hardware, and operating environment.

No guarantee is made that these files are complete, correct, or suitable for any particular application. Use at your own risk.
