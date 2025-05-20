import sounddevice as sd
import numpy as np
import librosa
import sounddevice as sd
import numpy as np
import parselmouth
import csv

def karplus_strong(
    freq,
    duration=1.0,
    sample_rate=44100,
    decay=0.996,
    brightness=0.5,
    volume=0.5  # 0.0 = silent, 1.0 = max
):
    N = int(sample_rate / freq)
    
    # Initial buffer with brightness shaping
    buf = (np.random.rand(N) - 0.5) * 2
    buf = buf * brightness + (1 - brightness) * np.hamming(N)

    samples = []

    for _ in range(int(sample_rate * duration)):
        avg = decay * 0.5 * (buf[0] + buf[1])
        samples.append(avg)
        buf = np.append(buf[1:], avg)

    waveform = np.array(samples)
    
    # Apply volume scaling and prevent clipping
    waveform *= volume / np.max(np.abs(waveform))
    
    return waveform

def play(pitch):
    note = karplus_strong(freq=pitch, duration=0.1, decay=0.99, brightness=0.8, volume=0.5)
    sd.play(note, samplerate=44100)
    sd.wait()

def record_audio(duration=1.0, samplerate=44100):
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
    sd.wait()
    return audio.flatten(), samplerate

def detect_pitch_parselmouth(audio, sr, time_step=0.01, pitch_floor=50, pitch_ceiling=500):
    snd = parselmouth.Sound(audio, sampling_frequency=sr)
    pitch = snd.to_pitch(time_step=time_step, pitch_floor=pitch_floor, pitch_ceiling=pitch_ceiling)
    pitch_values = pitch.selected_array['frequency']
    pitch_values = pitch_values[pitch_values > 0]  # Ignore unvoiced frames

    if len(pitch_values) == 0:
        return None

    median_pitch = np.median(pitch_values)
    return median_pitch

def test_parselmouth_pitch():
    audio, sr = record_audio()
    freq = detect_pitch_parselmouth(audio, sr)

    if freq:
        print(f" Detected pitch: {freq:.2f} Hz")
        play(freq)
    else:
        print("No pitch detected. Try again.")

def record_audio(duration=1.0, samplerate=44100):
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float64')
    sd.wait()
    return audio.flatten(), samplerate

def detect_pitch(audio, sr, pitch_floor=50, pitch_ceiling=500, min_accepted_pitch=75):
    snd = parselmouth.Sound(audio, sampling_frequency=sr)
    pitch = snd.to_pitch(pitch_floor=pitch_floor, pitch_ceiling=pitch_ceiling)
    freqs = pitch.selected_array['frequency']
    freqs = freqs[freqs > 0]
    if len(freqs) == 0:
        return None
    median_freq = float(np.median(freqs))
    if median_freq < min_accepted_pitch:
        return None  # Filter out pitches below threshold
    return median_freq

def capture_pitch_groups(n_groups=12):
    all_groups = []

    for group_idx in range(n_groups):
        print(f"\nGroup {group_idx + 1}/{n_groups} - Change String {(group_idx - 1) % 6 + 1}")
        group = []

        for string_idx in range(6):
            print(f"\nRecord String {string_idx + 1}/6:")
            while True:
                audio, sr = record_audio()
                freq = detect_pitch(audio, sr)

                if freq:
                    print(f"Detected pitch: {freq:.2f} Hz")
                    play(freq)
                    confirm = input("Press any key to delete, or [Enter] to keep: ").strip()
                    if confirm:
                        print("Pitch discarded. Try again.")
                    else:
                        group.append(freq)
                        break
                else:
                    print("No pitch detected. Try again.")

        all_groups.append(group)

    return all_groups

pitch_groups = capture_pitch_groups(n_groups=24)
with open('pitches.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(pitch_groups)
print(pitch_groups)