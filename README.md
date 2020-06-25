# whistle
Whistle controls output pins on a Raspberry Pi by detecting whistles, singing notes, etc.

See file 'pkgs_to_install' for required Python packages.

Aubio (https://aubio.org/) is used as the audio analyzer.  Currently, the
''yinfast'' algorithm is used for detection.  You can try experimenting
with other algorithms.  See: https://aubio.org/manual/latest/py_analysis.html



```
usage: whistle.py [-h] [-g GUARD_PITCHES] [-p PITCHES] [-o OUTPUT_PINS]
                  [-l PIN_HIGH_DELAY] [-v PITCH_VARIANCE] [-n NOTE_MILLIS]
                  [-i INPUT_AUDIO_DEVICE] [-d OUTPUT_AUDIO_DEVICE] [-a] [-s]

optional arguments:
  -h, --help            show this help message and exit
  -g GUARD_PITCHES, --guard_pitches GUARD_PITCHES
                        guard note pitches as csv list, default: 1630,1300
  -p PITCHES, --pitches PITCHES
                        action pitches as csv list, default: 550,670,830,930
  -o OUTPUT_PINS, --output_pins OUTPUT_PINS
                        output pins as csv list, default: 7,15,29,37
  -l PIN_HIGH_DELAY, --pin_high_delay PIN_HIGH_DELAY
                        pin high delay as csv list, default: 0,0,4,4
  -v PITCH_VARIANCE, --pitch_variance PITCH_VARIANCE
                        pitch variance hz, default:
  -n NOTE_MILLIS, --note_millis NOTE_MILLIS
                        milliseconds for each guard note pitch, min=100,
                        max=1000, default: 275
  -i INPUT_AUDIO_DEVICE, --input_audio_device INPUT_AUDIO_DEVICE
                        input audio device, default: 0
  -d OUTPUT_AUDIO_DEVICE, --output_audio_device OUTPUT_AUDIO_DEVICE
                        output audio device, default: -1
  -a, --audio_devices   list audio devices and exit
  -s, --sample          continously print detected frequency pitches, ^C to
                       exit
````


Notes on options:

- **Guard Pitches** (-g) These must be completed in order to unlock the action pitches.
  Guards pitches can be as few as one pitch, or multiple.

- **Note milliseconds** (-n) This specifies the length of a note for guards and actions.

- **Pitch Variance** (-v) This allow notes to be slightly off, plus or minus this value in Hertz.
   Unless you have perfect pitch, you probably need this.

- **Audio Devices** (-i and -o) PyAudio assigns a name an number to each audio device. You can
   specify these options as either an integer, or a substring of the name.  For instance, if
   you have 'Generic USB Audio' device, you can specify **-i usb**   Use the **-a** option
   to list devices.

- **Print samples** (-s) This allows you to simply print the detected pitch.  Not all frequencies
  may be detected, due to harmonics, noise, sample rates, particular FFT algorithms, etc.
