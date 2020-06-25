
# audio devices can be specified on command line as either a
# number or substring of a name.  
#  python whistle.py  [ input_device [ output_device ] ]

###########################################################
# Pyaudio devices, number of input channels, sample rate

# Audio input device 'None' for default
DEV = None

# OUT_DEV 'None' for default, or -1 for no output
OUT_DEV = -1

# number of recording channels, probably 1
CH = 1

# audio capture reate
AUDIO_STREAM_RATE = 44100
OUTPUT_BITRATE = 16000

# samples size should be power of two (required by analyse package)
SAMPLE_SIZE = 2048
#SAMPLE_SIZE = 4096
#SAMPLE_SIZE = 8192
#SAMPLE_SIZE = 16384

###########################################################
# Pitch detection, gpio action pins, number of samples required

# pitch for an note can vary by this hz
PITCH_VARIANCE = 35

# define pitches that relate to actions: 0-3
PITCHES = [ 500, 670, 830, 930 ]

# define action GPIO pinouts on Pi board, same number as PITCHES, see: https://pinout.xyz/#
ACTION_PINOUTS = [ 7, 15, 29, 37 ]

# number of consecutive samples to count as a note
# i.e., (SAMPLE_SIZE / AUDIO_STREAM_RATE) seconds each note
NOTE_SAMPLE_COUNT = 6
MINIMUM_GUARD_NOTES = 3

# define a sequnce of pitches, at least one note length each
# to activate action
GUARD_PITCH_SEQUENCE = [ 830, 670 ]

# once guard is actived, wait for up to this many seconds, e.g. number samples of silence
# for activation pitches
SECONDS_OF_SILENCE = 5
UNGUARDED_ACTIVE_SILENCE_COUNT = int( SECONDS_OF_SILENCE / (float(SAMPLE_SIZE) / float(AUDIO_STREAM_RATE)) )

###########################################################

import sys
import math
import numpy
import pyaudio
import analyse
try:
    import RPi.GPIO as GPIO
except:
    # allow to continue on import gpio failure
    pass


def get_sample_freq():
    # Read raw microphone data
    # rawsamps = STREAM.read(SAMPLE_SIZE)
    rawsamps = STREAM.read(SAMPLE_SIZE, exception_on_overflow = False)

    # Convert raw data to NumPy array
    samps = numpy.fromstring(rawsamps, dtype=numpy.int16)
    freq = analyse.detect_pitch(samps)

    # analyse erroneously reports 1002.2727...  often, so disregard
    if freq != None and int(freq) == 1002:
        freq = None

    return freq


def print_sample_freq():
    while True:
        freq = get_sample_freq()
        print freq
    

def is_expected_freq(actual, expected, variance):
    return (expected - variance) < actual and (expected + variance) > actual 
    

def get_first_sample():
    freq = get_sample_freq()
    while freq == None:
        freq = get_sample_freq()

    return freq


def get_first_sample_at_most(maxcount):
    i = 1 
    freq = get_sample_freq()
    while freq == None:
        i = i + 1
        if (i >= maxcount):
            break
        freq = get_sample_freq()

    return freq


def wait_for_guard():
    #play_wave(READY_JINGLE)
    print ''
    print 'guard waiting'
    freq = get_first_sample()
    state = 0

    while state < len(GUARD_PITCH_SEQUENCE):
        expected = GUARD_PITCH_SEQUENCE[state]
        expected_count = 0
        print '  state=', state
        print '    expecting=',expected,' actual=',freq

        for i in xrange(NOTE_SAMPLE_COUNT):

            if is_expected_freq(freq, expected, PITCH_VARIANCE):
                expected_count = expected_count + 1

            freq = get_sample_freq()
            print '    expecting=',expected,' actual=',freq


        # check if we got some correct guard freqencies
        if expected_count >= MINIMUM_GUARD_NOTES:
            state = state + 1
             
            # allow recognized state to persist until frequency changes
            while is_expected_freq(freq, expected, PITCH_VARIANCE):
                print '      extra', freq
                freq = get_sample_freq()

            # get another sample, allowing for silence
            freq = get_first_sample_at_most(NOTE_SAMPLE_COUNT/2)

        else:
            print 'guard NOT completed, need ',MINIMUM_GUARD_NOTES,', got ',expected_count
            #play_wave(GUARD_NOT_COMPLETE)
            #wait_for_silence()

            state = 0
            # play guard waiting
            print ''
            print 'guard waiting'

            #play_wave(READY_JINGLE)
            #wait_for_silence()
            freq = get_first_sample()

    # all states completed
    # play guard sequence completed
    print '==>> GUARD SEQUENCE COMPLETED'
    return True


def find_action(freq):
    freq = get_first_sample_at_most(NOTE_SAMPLE_COUNT*2)
    action = 0
    while action < len(PITCHES):
        expected = PITCHES[action]
        print 'testing freq ',freq,' for action: ', action,' expecting: ',expected
        if is_expected_freq(freq, expected, PITCH_VARIANCE):
            expected_count = 0
            for i in xrange(NOTE_SAMPLE_COUNT):
                if is_expected_freq(freq, expected, PITCH_VARIANCE):
                    expected_count = expected_count + 1
                freq = get_first_sample_at_most(NOTE_SAMPLE_COUNT)

            if expected_count >= MINIMUM_GUARD_NOTES:
                print 'FOUND ACTION: ', action
                return action
        else:
            action = action + 1

    return -1


def wait_for_silence():
    freq = get_sample_freq()
    count = 0
    while count < NOTE_SAMPLE_COUNT:
        if freq == None:
            count = count + 1
            freq = get_sample_freq()
        else:
            count = 0
            freq = get_sample_freq()


def turn_on_pin(pin):
    try:
        GPIO.output(pin, True)
    except:
        pass

def turn_off_pin(pin):
    try:
        GPIO.output(pin, False)
    except:
        pass

def run_detect():
    while True:
        wait_for_guard()
        wait_for_silence()
        print 'start action sound.....'
        active = True
        while active:

            # try to get a freqency action, up to 3 times
            freq = get_first_sample_at_most(UNGUARDED_ACTIVE_SILENCE_COUNT)
            if freq == None:
                active = False
                break

            # we have a pitch, try to find if it is an action pitch
            action = find_action(freq)
            if action == -1:
                continue

            # found action, get corresponding gpio pin
            expected = PITCHES[action]
            action_pin = ACTION_PINOUTS[action]

            # and loop while that pitch is detected
            freq = get_sample_freq()
            while is_expected_freq(freq, expected, PITCH_VARIANCE):
                print action
                # perform open/close action on rasp pi
                turn_on_pin(action_pin)
                freq = get_sample_freq()
    
            turn_off_pin(action_pin) 

            # end of while is_expected loop

        # end of while active loop

    # end of while true main loop
        
        

def generate_sines(list_freqs, tone_length, bitrate ):
    numberofframes = int(bitrate * tone_length)
    wavedata = ''
    for i in xrange(len(list_freqs)):
        frequency = list_freqs[i]
        for x in xrange(numberofframes):
            wavedata = wavedata + chr(int(math.sin(x/((bitrate/frequency)/math.pi)) * 127 + 128))

    return wavedata

    
def play_guard_notes(list_freqs):
    length_output_tones = (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) * NOTE_SAMPLE_COUNT
    wave = generate_sines(list_freqs, length_output_tones, OUTPUT_BITRATE)
    play_wave(wave)

def play_wave(wave):
    if OUT_DEV == -1:
        return
    OUTPUT_STREAM.start_stream()
    OUTPUT_STREAM.write(wave)
    OUTPUT_STREAM.stop_stream()


def find_audio_device(s):
    # if s is an integer string return it,
    # otherwise, look in pyaudio devices for a substring match
    if s.startswith('-') and s[1:].isdigit():
        return s
    if s.isdigit():
        return s
    s = s.lower()
    for i in range(pyaud.get_device_count()):
        dev = pyaud.get_device_info_by_index(i)
        ind = dev['index']
        name = dev['name'].lower()
        if s in name:
            return ind
    return -1


def print_audio_devices():    
    print 'Audio devices ======================================='
    for i in range(pyaud.get_device_count()):
        dev = pyaud.get_device_info_by_index(i)
        print dev['index'], dev['name'], 'channels:', dev['maxInputChannels'], 'defaultSampleRate', dev['defaultSampleRate']



READY_JINGLE = generate_sines( [ 800, 1600 ], .20, OUTPUT_BITRATE)
GUARD_NOT_COMPLETE = generate_sines( [ 333 ], .20, OUTPUT_BITRATE)

note_length_output = (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) * NOTE_SAMPLE_COUNT
GUARD_ACTIVATE = generate_sines(GUARD_PITCH_SEQUENCE, note_length_output, OUTPUT_BITRATE)



####################################################

# Initialize PyAudio
pyaud = pyaudio.PyAudio()


# get command line override for audio input, audio output

if len(sys.argv) == 2 and sys.argv[1] == '-h':
    print 'usage:  python ',sys.argv[0], ' [ audio_input_name_or_number  [ audio_output_name_or_number ] ]'
    print ''
    print_audio_devices()
    pyaud.terminate()
    exit()
    
if len(sys.argv) >= 2:
    DEV = find_audio_device(sys.argv[1])
if len(sys.argv) >= 3:
    OUT_DEV = find_audio_device(sys.argv[2])

print ' Using input device number: ', DEV
print 'Using output device number: ', OUT_DEV



STREAM = pyaud.open(
    format = pyaudio.paInt16,
    channels = CH,
    rate = AUDIO_STREAM_RATE,
    input_device_index = DEV,
    input = True)

if OUT_DEV != -1:
    OUTPUT_STREAM = pyaud.open(format = pyaud.get_format_from_width(1),
                channels = 1,
                output_device_index = OUT_DEV,
                rate = OUTPUT_BITRATE,
                start = False,
                output = True)
    OUTPUT_STREAM.stop_stream()


# initialize Rasp Pi for GPIO
try:
    GPIO.setmode(GPIO.BOARD)
    for pin in ACTION_PINOUTS:
        GPIO.setup(pin, GPIO.OUT)
except:
    pass

#play_guard_notes(GUARD_PITCH_SEQUENCE)


#####################################################
# main detection loop

try:
    run_detect()
except KeyboardInterrupt:
    print("*** Ctrl+C pressed, exiting")





# shutdown audio input, and output (if opened)
STREAM.stop_stream()
STREAM.close()
if OUT_DEV != -1:
    OUT_STREAM.stop_stream()
    OUT_STREAM.close()
pyaud.terminate()


# shutdown gpio
try:
    for pin in ACTION_PINOUTS:
        GPIO.output(pin,False)
    GPIO.cleanup()
except:
    pass


