// tuningInterface.js - Revised to ensure no button reuse

class TuningInterface {
  constructor(tuner, notes, meter) {
    this.tuner = tuner;
    this.notes = notes;
    this.meter = meter;
    this.isInterfaceActive = false;
    this.currentStringIndex = 0;
    this.detectedPitches = [];
    this.targetFrequencies = [329.63, 246.94, 196.00, 146.83, 110.00, 82.41];
    this.stringNames = ["E4 (1st)", "B3 (2nd)", "G3 (3rd)", "D3 (4th)", "A2 (5th)", "E2 (6th)"];
    this.tuningInProgress = false;
    this.tuningMode = 'record';
    this.originalCallback = null;

    this.setupUI();
  }

  setupUI() {
    const container = document.createElement('div');
    container.className = 'tuning-interface';
    container.style.cssText = 'position:fixed; bottom:20px; left:0; right:0; text-align:center; display:none; background-color:rgba(255,255,255,0.9); padding:15px; border-radius:10px 10px 0 0; box-shadow:0 -2px 10px rgba(0,0,0,0.1)';

    this.stringIndicator = document.createElement('div');
    this.stringIndicator.className = 'string-indicator';
    this.stringIndicator.style.cssText = 'font-size:24px; margin-bottom:10px';
    this.stringIndicator.textContent = 'String: E4 (1st)';

    this.statusMessage = document.createElement('div');
    this.statusMessage.className = 'status-message';
    this.statusMessage.style.cssText = 'margin-top:10px; font-size:16px';
    this.statusMessage.textContent = 'Ready to record';

    this.recordButton = this.createButton('Record String', '#2c3e50', this.recordString.bind(this));
    this.tuneButton = this.createButton('Start Tuning', '#2980b9', this.startStringTuning.bind(this));
    this.tuneButton.style.display = 'none';

    container.appendChild(this.stringIndicator);
    container.appendChild(this.recordButton);
    container.appendChild(this.tuneButton);
    container.appendChild(this.statusMessage);
    document.body.appendChild(container);

    const toggleButton = this.createButton('Guitar Tuner', '#2c3e50', this.toggleInterface.bind(this));
    toggleButton.style.position = 'fixed';
    toggleButton.style.bottom = '20px';
    toggleButton.style.right = '20px';
    document.body.appendChild(toggleButton);

    this.container = container;
  }

  createButton(text, bgColor, onClick) {
    const btn = document.createElement('button');
    btn.className = 'temp-ui-element';
    btn.textContent = text;
    btn.style.cssText = `padding:10px 20px; font-size:16px; border-radius:5px; background-color:${bgColor}; color:white; border:none; cursor:pointer; margin:5px;`;
    btn.addEventListener('click', onClick);
    return btn;
  }

  toggleInterface() {
    this.isInterfaceActive = !this.isInterfaceActive;
    this.container.style.display = this.isInterfaceActive ? 'block' : 'none';

    if (this.isInterfaceActive) {
      this.originalCallback = this.tuner.onNoteDetected;
      this.resetTuningProcess();
    } else {
      this.cleanupUI();
      this.tuner.onNoteDetected = this.originalCallback || this.defaultNoteHandler;
      if (this.tuner.stopOscillator) this.tuner.stopOscillator();
    }
  }

  defaultNoteHandler(note) {
    if (app.notes.isAutoMode && app.lastNote === note.name) {
      app.update(note);
    } else {
      app.lastNote = note.name;
    }
  }

  cleanupUI() {
    [...this.container.querySelectorAll('.temp-ui-element')].forEach(el => el.remove());
    this.container.appendChild(this.recordButton);
    this.container.appendChild(this.tuneButton);
  }

  resetTuningProcess() {
    this.cleanupUI();
    this.currentStringIndex = 0;
    this.detectedPitches = [];
    this.updateStringIndicator();
    this.statusMessage.textContent = 'Ready to record';
    this.recordButton.style.display = 'inline-block';
    this.tuneButton.style.display = 'none';
    this.tuningMode = 'record';
    this.tuningInProgress = false;
  }

  updateStringIndicator() {
    this.stringIndicator.textContent = `String: ${this.stringNames[this.currentStringIndex]}`;
  }

  recordString() {
    if (this.tuningInProgress) return;
    this.tuningInProgress = true;
    this.statusMessage.textContent = 'Play the string clearly...';
    this.recordButton.textContent = 'Recording...';

    const detected = [];
    const startTime = Date.now();
    const self = this;

    const previousCallback = this.originalCallback;
    this.tuner.onNoteDetected = function(note) {
      if (previousCallback) previousCallback(note);
      if (Date.now() - startTime > 1000) {
        self.tuner.onNoteDetected = self.originalCallback;
        self.finishRecording(detected);
      }
      if (note && note.frequency) detected.push(note.frequency);
    };

    setTimeout(() => {
      if (this.tuningInProgress) {
        this.tuner.onNoteDetected = this.originalCallback;
        this.finishRecording(detected);
      }
    }, 3000);
  }

  finishRecording(frequencies) {
    frequencies = frequencies.filter(f => f >= 60 && f <= 375);
    if (frequencies.length === 0) {
      this.statusMessage.textContent = 'No pitch detected. Try again.';
      this.recordButton.textContent = 'Record String';
      this.tuningInProgress = false;
      return;
    }

    frequencies.sort((a, b) => a - b);
    const median = frequencies[Math.floor(frequencies.length / 2)];
    this.detectedPitches[this.currentStringIndex] = median;
    this.statusMessage.textContent = `Detected: ${median.toFixed(2)} Hz`;
    this.recordButton.style.display = 'none';

    const confirm = this.createButton('Keep this reading', '#27ae60', () => {
      this.currentStringIndex++;
      if (this.currentStringIndex < 6) {
        this.updateStringIndicator();
        this.statusMessage.textContent = 'Ready to record';
        this.recordButton.textContent = 'Record String';
        this.recordButton.style.display = 'inline-block';
        confirm.remove();
        retry.remove();
      } else {
        confirm.remove();
        retry.remove();
        this.sendPitchesToBackend();
      }
    });

    const retry = this.createButton('Try again', '#e74c3c', () => {
      this.recordButton.textContent = 'Record String';
      this.statusMessage.textContent = 'Ready to record';
      this.recordButton.style.display = 'inline-block';
      confirm.remove();
      retry.remove();
    });

    this.container.appendChild(confirm);
    this.container.appendChild(retry);
    this.tuningInProgress = false;
  }

  sendPitchesToBackend() {
    this.statusMessage.textContent = 'Processing tuning data...';
    this.recordButton.style.display = 'none';
    this.tuneButton.style.display = 'none';

    fetch('/tune_guitar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pitches: this.detectedPitches })
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        this.tuningMode = 'tune';
        this.currentStringIndex = 0;
        this.targetFrequencies = data.target_frequencies;
        this.updateStringIndicator();
        this.statusMessage.textContent = 'Ready to tune';
        this.tuneButton.style.display = 'inline-block';
      } else {
        this.statusMessage.textContent = `Error: ${data.error || 'Unknown error'}`;
      }
    })
    .catch(() => {
      this.statusMessage.textContent = 'Connection error, please try again.';
    });
  }

  startStringTuning() {
    const target = this.targetFrequencies[this.currentStringIndex];
    this.statusMessage.textContent = `Tune to ${target.toFixed(2)} Hz`;
    this.tuneButton.style.display = 'none';

    const meter = document.createElement('div');
    meter.className = 'tuning-meter temp-ui-element';
    meter.style.cssText = 'height:40px; position:relative; margin:20px auto; width:80%; background-color:#ecf0f1; border-radius:20px';

    const indicator = document.createElement('div');
    indicator.style.cssText = 'position:absolute; height:100%; width:10px; background-color:#e74c3c; left:50%; transform:translateX(-50%); border-radius:5px; transition:left 0.2s ease-out, background-color 0.2s ease-out';
    meter.appendChild(indicator);

    const centerLine = document.createElement('div');
    centerLine.style.cssText = 'position:absolute; height:100%; width:2px; background-color:#7f8c8d; left:50%; transform:translateX(-50%); opacity:0.5;';
    meter.appendChild(centerLine);

    const status = document.createElement('div');
    status.className = 'temp-ui-element';
    status.style.cssText = 'text-align:center; margin-top:10px; font-size:20px; font-weight:bold';
    status.textContent = 'Play the string';

    this.container.appendChild(meter);
    this.container.appendChild(status);

    const done = this.createButton('String in Tune', '#2ecc71', () => {
      this.tuner.onNoteDetected = this.originalCallback;
      meter.remove();
      status.remove();
      done.remove();

      this.currentStringIndex++;
      if (this.currentStringIndex < 6) {
        this.updateStringIndicator();
        this.tuneButton.style.display = 'inline-block';
        this.statusMessage.textContent = 'Ready to tune';
      } else {
        this.statusMessage.textContent = 'Guitar tuning complete';
      }
    });

    this.container.appendChild(done);

    const self = this;
    const previousCallback = this.originalCallback;
    this.tuner.onNoteDetected = function(note) {
      if (previousCallback) previousCallback(note);
      if (!note || !note.frequency) return;

      const diff = note.frequency - target;

      // Ignore if frequency is more than 10 Hz off
      if (Math.abs(diff) > 10) return;

      const percent = Math.min(Math.max(diff / 10, -1), 1);
      indicator.style.left = `${50 + percent * 50}%`;

      if (Math.abs(diff) < 1) {
        indicator.style.backgroundColor = '#2ecc71';
        status.textContent = '✓ In tune!';
      } else if (diff > 0) {
        indicator.style.backgroundColor = '#e74c3c';
        status.textContent = '↓ Too high';
      } else {
        indicator.style.backgroundColor = '#3498db';
        status.textContent = '↑ Too low';
      }
    };
  }
}
