# app.py
from flask import Flask, request, jsonify
import sys
import os
import json

# Add the directory containing your tuning modules to the path
# Replace with your actual path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your tuning functions
from simulation import Guitar, tune_all_targets, find_equilibrium, calculate_frequencies

app = Flask(__name__)

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/tune_guitar', methods=['POST'])
def tune_guitar():
    data = request.json
    if not data or 'pitches' not in data:
        return jsonify({'success': False, 'error': 'No pitch data provided'})
    
    pitches = data['pitches']
    if len(pitches) != 6:
        print(pitches)
        return jsonify({'success': False, 'error': 'Expected 6 string pitches'})
    
    try:
        # Use your guitar model (adjust this based on your setup)
        # guitar = Guitar([0.004192943344892194,0.0527210733243767,60000.00002754921,
        #                  15646.363451143618,26442.354190429935,45217.99026649949,
        #                  105769.4166681145,202776.86981479632,331077.04979176837,
        #                  72.52514720114756,68.78669744260682,74.10451752256648,
        #                  97.27716521435585,104.6707057014392,95.92022163385528,
        #                  0.4714008471583247,0.8239609365225877,0.4713989423688511,
        #                  0.4655332067198231,0.8298406813954923,0.4655924432686475,
        #                  0.00018279946433012137,0.000134444695428939,0.0006431422682395684,
        #                  0.004840009035441805,0.002416111700068022,0.009151670624607467])
        guitar = Guitar([0.003999999999999999,0.05524938811609182,60000.00007204304,15646.363464920685,26442.35421639301,45217.990315999006,105769.41665287623,202776.86981357756,331077.04982716136,72.52512062656356,68.78663780217832,74.10452394971462,97.27718738731768,104.6706993118599,95.92026722935172,0.8368477731442122,0.836817275027336,0.4585183847445688,0.8368437423578716,0.8367803831731069,0.4588194505632681,8.358488981090071e-05,0.000134444695428939,0.0008182382235060834,0.0017961154597214424,0.00322602427328139,0.014614149157429299])
        
        # Standard tuning target frequencies
        tuned_freq = [329.63, 246.94, 196.00, 146.83, 110.00, 82.41]  # E4, B3, G3, D3, A2, E2
        
        # Determine the offsets needed for the current state
        detuned_offsets = tune_all_targets(pitches, guitar, initial_offset=None)
        
        # Determine the offsets needed for standard tuning
        tuned_offsets = tune_all_targets(tuned_freq, guitar, initial_offset=None)
        
        # Calculate intermediate tuning steps for each string
        target_frequencies = []
        offsets = detuned_offsets.copy()
        
        for i in range(6):
            offsets[i] = tuned_offsets[i]
            x = find_equilibrium(offsets, guitar)
            freq = calculate_frequencies(x, offsets, guitar)
            if freq is None:
                return jsonify({
                    'success': False,
                    'error': 'Invalid Tunings for a Guitar'
                })

            target_frequencies.append(float(freq[i]))
        
        return jsonify({
            'success': True,
            'target_frequencies': target_frequencies
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)
