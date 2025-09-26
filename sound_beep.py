import pyaudio
import numpy as np
import time

def generate_sine_wave(frequency=440, duration=1.0, sample_rate=44100, amplitude=0.5):
    """
    Generate a sine wave tone
    
    Args:
        frequency: Frequency in Hz (default: 440Hz - A4 note)
        duration: Duration in seconds (default: 1.0s)
        sample_rate: Samples per second (default: 44100)
        amplitude: Amplitude (0.0 to 1.0, default: 0.5)
    """
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Generate sine wave
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    
    return wave.astype(np.float32)

def play_tone(frequency=440, duration=1.0):
    """
    Play a sine wave tone using PyAudio
    """
    # Generate the sine wave
    samples = generate_sine_wave(frequency, duration)
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # Open stream
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=44100,
                    output=True)
    
    # Play the sound
    stream.write(samples.tobytes())
    
    # Clean up
    stream.stop_stream()
    stream.close()
    p.terminate()

# Example usage
if __name__ == "__main__":
    print("Playing A4 note (440Hz) for 2 seconds...")
    play_tone(800, 0.50)