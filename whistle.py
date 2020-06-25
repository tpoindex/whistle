DEV = 10
CH = 1

# audio capture reate
AUDIO_STREAM_RATE = 44100
OUTPUT_BITRATE = 16000

# samples size should be power of two (required by analyse package)
SAMPLE_SIZE = 8192
#SAMPLE_SIZE = 16384

# pitch for an note can vary by this hz
PITCH_VARIANCE = 10

# define pitches that relate to actions: 0-3
PITCHES = [ 83, 105, 128, 170 ]

# number of consecutive samples to count as a note
# i.e., (SAMPLE_SIZE / AUDIO_STREAM_RATE) seconds each note
NOTE_SAMPLE_COUNT = 3

# define a sequnce of pitches, at least one note length each
# to activate action
GUARD_PITCH_SEQUENCE = [ 83, 105, 170 ]


import math
import numpy
import pyaudio
import analyse

def get_sample_freq():
    # Read raw microphone data
    # rawsamps = STREAM.read(SAMPLE_SIZE)
    rawsamps = STREAM.read(SAMPLE_SIZE, exception_on_overflow = False)

    # Convert raw data to NumPy array
    samps = numpy.fromstring(rawsamps, dtype=numpy.int16)

    # Show the volume and pitch
    #print analyse.loudness(samps), analyse.detect_pitch(samps), analyse.musical_detect_pitch(samps)

    return analyse.detect_pitch(samps)


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

def wait_for_guard():
    # play guard waiting
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

        for i in range(NOTE_SAMPLE_COUNT):

            if is_expected_freq(freq, expected, PITCH_VARIANCE):
                expected_count = expected_count + 1

            freq = get_sample_freq()
            print '    expecting=',expected,' actual=',freq


        # check if we got some correct guard freqencies
        if expected_count >= NOTE_SAMPLE_COUNT - 1:
            state = state + 1
             
            # allow recognized state to persist until frequency changes
            while is_expected_freq(freq, expected, PITCH_VARIANCE):
                print '      extra', freq
                freq = get_sample_freq()
        else:
            # play guard not completed
            print 'guard NOT completed'
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
    action = 0
    while action < len(PITCHES):
        print 'testing action: ', action
        expected = PITCHES[action]
        if is_expected_freq(freq, expected, PITCH_VARIANCE):
            expected_count = 0
            for i in range(NOTE_SAMPLE_COUNT):
                if is_expected_freq(freq, expected, PITCH_VARIANCE):
                    expected_count = expected_count + 1
                freq = get_sample_freq()

            if expected_count >= NOTE_SAMPLE_COUNT - 1:
                print 'found action: ', action
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


def run_detect():
    while True:
        wait_for_guard()
        wait_for_silence()
        print 'start action sound.....'
        freq = get_first_sample()
        action = find_action(freq)
        expected = PITCHES[action]
        while is_expected_freq(get_sample_freq(), expected, PITCH_VARIANCE):
            print action
            # perform open/close action on rasp pi
        
        

def generate_sines(list_freqs, tone_length, bitrate ):
    numberofframes = int(bitrate * tone_length)
    wavedata = ''
    print 'generate '
    for i in range(len(list_freqs)):
        frequency = list_freqs[i]
        for x in xrange(numberofframes):
            wavedata = wavedata + chr(int(math.sin(x/((bitrate/frequency)/math.pi)) * 127 + 128))

    return wavedata

    
def play_guard_notes(list_freqs):
    length_output_tones = (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) * NOTE_SAMPLE_COUNT
    wave = generate_sines(list_freqs, length_output_tones, OUTPUT_BITRATE)
    play_wave(wave)

def play_waveOLD(wave, bitrate):
    outstream = pyaud.open(format = pyaud.get_format_from_width(1),
                channels = 1,
                output_device_index = DEV,
                rate = bitrate,
                output = True)
    print 'write '
    outstream.write(wave)
    print 'stop '
    outstream.stop_stream()
    print 'close'
    outstream.close()

    
def play_wave(wave):
    OUTPUT_STREAM.start_stream()
    OUTPUT_STREAM.write(wave)
    OUTPUT_STREAM.stop_stream()

    

READY_JINGLE = generate_sines( [ 800, 1600 ], .20, OUTPUT_BITRATE)
GUARD_NOT_COMPLETE = generate_sines( [ 333 ], .20, OUTPUT_BITRATE)

note_length_output = (float(SAMPLE_SIZE) / AUDIO_STREAM_RATE) * NOTE_SAMPLE_COUNT
GUARD_ACTIVATE = generate_sines(GUARD_PITCH_SEQUENCE, note_length_output, OUTPUT_BITRATE)


# Initialize PyAudio
pyaud = pyaudio.PyAudio()

STREAM = pyaud.open(
    format = pyaudio.paInt16,
    channels = CH,
    rate = AUDIO_STREAM_RATE,
    input_device_index = DEV,
    input = True)

OUTPUT_STREAM = pyaud.open(format = pyaud.get_format_from_width(1),
                channels = 1,
                output_device_index = DEV,
                rate = OUTPUT_BITRATE,
                output = True)
OUTPUT_STREAM.stop_stream()


play_guard_notes(GUARD_PITCH_SEQUENCE)
run_detect()

#print_sample_freq()


