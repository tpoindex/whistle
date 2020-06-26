#!/usr/bin/python

# audio devices can be specified on command line as either a
# number or substring of a name.  
#  python whistle.py  [ input_device [ output_device ] ]

import argparse
import sys
import math
import numpy
import pyaudio
import aubio
try:
    import RPi.GPIO as GPIO
except:
    # allow to continue on import gpio failure
    pass

###########################################################
# Pyaudio devices, number of input channels, sample rate

# Audio input device 'None' for default
DEV = 0

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

# aubio 
TOLERANCE = 0.40
CONFIDENCE_LEVEL = 0.50
WIN_S = 2048
HOP_S = SAMPLE_SIZE
FFT_METHOD = "yinfast"

# FFT_METHOD = "default"
# note that some FFT methods don't report confidence level, so adjust accordingly

###########################################################
# Pitch detection, gpio action pins, number of samples required

# pitch for an note can vary by this hz
PITCH_VARIANCE = 35

# define pitches that relate to actions: 0-3
PITCHES = [ 550, 670, 830, 930 ]

# define action GPIO pinouts on Pi board, same number as PITCHES, see: https://pinout.xyz/#
ACTION_PINOUTS = [ 7, 15, 29, 37 ]

# define number of seconds that corresponding pin should be high after pitch is lost
PIN_HIGH_DELAY = [ 0, 0, 4, 4 ]

# number of consecutive samples to count as a note for guard unlocking
# 275 ms is approx 6 samples of 2048 at 44.1khz
NOTE_MILLIS = 275
NOTE_SAMPLE_COUNT = int( (float(NOTE_MILLIS) / 1000) / (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) + 0.5)
MINIMUM_GUARD_NOTES = NOTE_SAMPLE_COUNT / 2
if MINIMUM_GUARD_NOTES == 0: MINIMUM_GUARD_NOTES = 1

# define a sequnce of pitches, at least one note length each
# to activate action
GUARD_PITCH_SEQUENCE = [ 1630, 1300 ]

# once guard is actived, wait for up to this many seconds, e.g. number samples of silence
# for activation pitches
SECONDS_OF_SILENCE = 5
UNGUARDED_ACTIVE_SILENCE_COUNT = int( SECONDS_OF_SILENCE / (float(SAMPLE_SIZE) / float(AUDIO_STREAM_RATE)) )


# mix and max freqs, ignore freqs outside this range
MAX_FREQ = 50
MIN_FREQ = 20000

def setMinMax():
    global MAX_FREQ, MIN_FREQ
    MAX_FREQ = max([max(PITCHES), max(GUARD_PITCH_SEQUENCE)]) + PITCH_VARIANCE
    MIN_FREQ = min([min(PITCHES), min(GUARD_PITCH_SEQUENCE)]) - PITCH_VARIANCE

setMinMax()


###########################################################
    

# get the aubio pitch object 
PITCH_O = aubio.pitch(FFT_METHOD, WIN_S, HOP_S, AUDIO_STREAM_RATE)
PITCH_O.set_tolerance(TOLERANCE)

def get_sample_freq():
    # Read raw microphone data
    # rawsamps = STREAM.read(SAMPLE_SIZE)
    rawsamps = STREAM.read(SAMPLE_SIZE, exception_on_overflow = False)

    # Convert raw data to NumPy array
    samps = numpy.fromstring(rawsamps, dtype=numpy.float32)
    freq = PITCH_O(samps)[0]
    confidence = PITCH_O.get_confidence()

    # print("{} / {}".format(freq,confidence))

    if freq < 1.0 or confidence < CONFIDENCE_LEVEL: 
        return None
    if freq < MIN_FREQ or freq > MAX_FREQ:
        return None

    return int(freq)


def sleep_audio(sec):
    # just read a number of samples in order to sleep
    # and keep the audio buffer empty while doing sleeping
    if sec <= 0: return
    numreads = int( float(sec) / (float(SAMPLE_SIZE) / float(AUDIO_STREAM_RATE)) ) 
    for i in xrange(numreads):
        STREAM.read(SAMPLE_SIZE, exception_on_overflow = False)


def print_sample_freq():
    while True:
        freq = get_sample_freq()
        if freq != None:
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
    print 'guard waiting for sequence: ', GUARD_PITCH_SEQUENCE
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
            print 'guard waiting for sequence: ', GUARD_PITCH_SEQUENCE

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

            # try to get an action pitch for up to SECONDS_OF_SILENCE seconds
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

            # read again and loop while that pitch is detected
            freq = get_sample_freq()
            first_time = True
            while is_expected_freq(freq, expected, PITCH_VARIANCE):
                if first_time:
                    print action, ' ON, pin: ', action_pin
                    first_time = False
                # perform open/close action on rasp pi
                turn_on_pin(action_pin)
                freq = get_sample_freq()
    
            # recognized pitch had stopped, delay before turning off (if any)
            delay_seconds = PIN_HIGH_DELAY[action]
            print action,' pitch lost, delaying off for ',delay_seconds,' seconds'
            sleep_audio(delay_seconds)
            print action,' OFF, pin: ', action_pin
            turn_off_pin(action_pin) 
            print 'waiting up to ',SECONDS_OF_SILENCE,' seconds for next command pitch, if any....'

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

def is_int_list(l):
    if len(l) == 0:
       return False
    try:
       map(int, l)
       return True
    except ValueError:
        return False

def mk_int_list(l):
    return map(int, l)

# Initialize PyAudio
pyaud = pyaudio.PyAudio()
print 'PyAudio initialized ================================='
print 


# parse options
parser = argparse.ArgumentParser()
parser.add_argument('-g', '--guard_pitches', dest='guard_pitches', action='store', type=str, help='guard note pitches as csv list, default: ' + ','.join(map(str,GUARD_PITCH_SEQUENCE)))
parser.add_argument('-p', '--pitches', dest='pitches', action='store', type=str, help='action pitches as csv list, default: ' + ','.join(map(str,PITCHES)))
parser.add_argument('-o', '--output_pins', dest='output_pins', action='store', type=str, help='output pins as csv list, default: ' + ','.join(map(str,ACTION_PINOUTS)))
parser.add_argument('-l', '--pin_high_delay', dest='pin_high_delay', action='store', type=str, help='pin high delay as csv list, default: ' + ','.join(map(str,PIN_HIGH_DELAY)))

parser.add_argument('-v', '--pitch_variance', dest='pitch_variance', action='store', type=int, help='pitch variance hz, default: ') # + str(PITCH_VARIANCE))
parser.add_argument('-n', '--note_millis', dest='note_millis', action='store', type=int, help='milliseconds for each guard note pitch, min=100, max=1000, default: ' + str(NOTE_MILLIS))

parser.add_argument('-i', '--input_audio_device', dest='input_audio_device', help='input audio device, default: ' + str(DEV))
parser.add_argument('-d', '--output_audio_device', dest='output_audio_device', help='output audio device, default: ' + str(OUT_DEV))

parser.add_argument('-a', '--audio_devices', dest='audio_devices', action='store_true', help='list audio devices and exit')
parser.add_argument('-s', '--sample', dest='sample', action='store_true', help='continously print detected frequency pitches, ^C to exit')

args = parser.parse_args()

if args.audio_devices:
    print_audio_devices()
    pyaud.terminate()
    exit()

if args.input_audio_device != None:
    DEV = int(find_audio_device(args.input_audio_device))
    if DEV == -1:
        print 'error, input_audio_device ', args.input_audio_device, 'not found'
        exit()

if args.output_audio_device != None:
    OUT_DEV = int(find_audio_device(args.output_audio_device))

if args.guard_pitches != None:
    l = args.guard_pitches.split(',')
    if is_int_list(l):
        GUARD_PITCH_SEQUENCE = mk_int_list(l)
        setMinMax()
    else:
        print 'error, --guard_pitches is not a comma separated list of integers'
        exit()

if args.pitches != None:
    l = args.pitches.split(',')
    if is_int_list(l):
        PITCHES = mk_int_list(l)
        setMinMax()
    else:
        print 'error, --pitches is not a comma separated list of integers'
        exit()

if args.output_pins != None:
    l = args.output_pins.split(',')
    if is_int_list(l):
        ACTION_PINOUTS = mk_int_list(l)
    else:
        print 'error, --output_pins is not a comma separated list of integers'
        exit()

if args.pin_high_delay != None:
    l = args.pin_high_delay.split(',')
    if is_int_list(l):
        PIN_HIGH_DELAY = l
    else:
        print 'error, --pin_high_delay is not a comma separated list of integers'
        exit()

if len(PITCHES) != len(ACTION_PINOUTS) or len(PITCHES) != len(PIN_HIGH_DELAY):
    print 'error, --pitches, --output_pins, and/or --pin_high_delay not of equal length'
    exit()

if args.pitch_variance != None:
    PITCH_VARIANCE = int(args.pitch_variance)
    setMinMax()

if args.note_millis != None:
    if args.note_millis < 100 or  args.note_millis > 1000:
        print 'error, --note_millis should be 100 to 1000'
        exit()
    NOTE_MILLIS = args.note_millis
    NOTE_SAMPLE_COUNT = int( (float(NOTE_MILLIS) / 1000) / (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) + 0.5)
    MINIMUM_GUARD_NOTES = NOTE_SAMPLE_COUNT / 2
    if MINIMUM_GUARD_NOTES == 0: MINIMUM_GUARD_NOTES = 1


print ' Using input device number: ', DEV
print 'Using output device number: ', OUT_DEV
print '                Audio rate: ', AUDIO_STREAM_RATE
print '               Sample size: ', SAMPLE_SIZE
print '          Note duration ms: ', NOTE_MILLIS
print '    Number of samples/note: ', NOTE_SAMPLE_COUNT
print '            Pitch variance: ', PITCH_VARIANCE
print '               Guard notes: ', GUARD_PITCH_SEQUENCE
print '              Action notes: ', PITCHES
print '               Action pins: ', ACTION_PINOUTS
print '       Pin high delay secs: ', PIN_HIGH_DELAY
print '             Minimum pitch: ', MIN_FREQ
print '             Maximum pitch: ', MAX_FREQ



# aubio pyaudio stream
STREAM = pyaud.open(
    format = pyaudio.paFloat32,
    channels = CH,
    rate = AUDIO_STREAM_RATE,
    input_device_index = DEV,
    input = True)

if args.sample:
    MAX_FREQ = 20000
    MIN_FREQ = 1
    try:
        print_sample_freq()
    except KeyboardInterrupt:
        print("*** Ctrl+C pressed, exiting")
        STREAM.stop_stream()
        STREAM.close()
        pyaud.terminate()
        exit()




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
    OUTPUT_STREAM.close()
pyaud.terminate()


# shutdown gpio
try:
    for pin in ACTION_PINOUTS:
        GPIO.output(pin,False)
    GPIO.cleanup()
except:
    pass


