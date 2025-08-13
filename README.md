NeoPixel Segment Controller (Arduino + Python GUI)

Control 5 chained NeoPixel segments from a Python GUI.
Segments: 0→8 LEDs, 1–4→9 LEDs each (total 44) on a single data line (Arduino pin 8).

What’s included

Arduino: arduino/neopixel_segments_varlen.ino — line-based serial protocol.

Python GUI: neo_segments_varlen_gui.py — responsive Tkinter app with per-segment RGB controls.

Hardware

MCU: Arduino Uno (or compatible)

LEDs: WS2812 / NeoPixel (5V), chained in this order:

Segment 0: 8 LEDs

Segments 1–4: 9 LEDs each

Wiring:

NeoPixel DIN → Arduino D8

GND shared between Arduino and LED power

5V sized for load (worst case ≈ 44 × 60 mA ≈ 2.6 A on full-white)

Recommended: 330–470 Ω resistor inline on DIN, 1000 µF cap across 5V/GND at strip start

Setup
1) Arduino

Open arduino/neopixel_segments_varlen.ino in the Arduino IDE.

Board: Arduino Uno, Port: your COM/tty.

Upload (baud in code is 9600).

2) Python GUI

Requirements: Python 3.8+
