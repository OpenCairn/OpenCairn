#!/usr/bin/env python3
"""Transcribe a 16kHz mono PCM WAV through installed Handy into timed chunks.

Output and diagnostics must be scratch paths outside the vault. Chunk bounds
are approximate; run WhisperX alignment before presenting word timestamps.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave

import numpy as np

MODEL = 'handy-computer/parakeet-tdt-0.6b-v3-gguf/parakeet-tdt-0.6b-v3-Q8_0.gguf'


def chunk_bounds(audio, rate=16000):
    """Partition all samples; choose a quiet 200ms window near each 30s bound."""
    bounds = [0]
    start = 0
    while len(audio) - start > 30 * rate:
        candidates = np.arange(start + 25 * rate, start + 30 * rate - 3200, 1600)
        end = int(min(candidates, key=lambda a: float(np.mean(
            audio[a:a + 3200].astype(float) ** 2)))) + 1600
        bounds.append(end)
        start = end
    bounds.append(len(audio))
    return list(zip(bounds, bounds[1:]))


def transcribe(wav_path, output, handy='handy', model=MODEL, allow_cpu=False):
    output = Path(output)
    if output.exists():
        raise ValueError('Output already exists; choose a fresh scratch path')
    with wave.open(str(wav_path)) as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (16000, 1, 2, 'NONE'):
            raise ValueError('Input must be uncompressed 16kHz mono signed 16-bit PCM WAV')
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').copy()
    if not len(audio):
        raise ValueError('Input WAV is empty')
    scratch = Path(tempfile.mkdtemp(prefix='handy-gguf-'))
    segments = []
    inference_seconds = 0
    backends = set()
    started = time.monotonic()
    for i, (a, b) in enumerate(chunk_bounds(audio)):
        path = scratch / f'{i:04d}.wav'
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(audio[a:b].tobytes())
        result = subprocess.run(
            [handy, '--transcribe-file', str(path), '--model', model, '--json'],
            capture_output=True, text=True, timeout=120,
        )
        (scratch / f'{i:04d}.log').write_text(result.stderr)
        (scratch / f'{i:04d}.jsonl').write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(f'Handy failed on chunk {i}; see {scratch}')
        lines = [line for line in result.stdout.splitlines() if line.strip().startswith('{')]
        row = json.loads(lines[-1])
        backend = row.get('bound_backend', '')
        backends.add(backend)
        gpu_bound = any(kind in backend.lower() for kind in ('vulkan', 'metal', 'cuda'))
        if not gpu_bound and not (allow_cpu and backend.lower() == 'cpu'):
            raise RuntimeError(f'No verified GPU binding ({backend!r}); see {scratch}. '
                               'Use --allow-cpu only for a deliberate CPU run.')
        if row.get('model') != model or not isinstance(row.get('text'), str):
            raise RuntimeError(f'Unexpected model/output on chunk {i}; see {scratch}')
        if abs(row['audio_secs'] - (b - a) / 16000) > 0.1:
            raise RuntimeError(f'Audio duration mismatch on chunk {i}; see {scratch}')
        inference_seconds += row['transcribe_ms'][0] / 1000
        segments.append({'start': a / 16000, 'end': b / 16000, 'text': row['text']})
    result = {
        'segments': segments, 'language': 'en', 'model': model,
        'engine_metadata': {
            'backend': sorted(backends), 'duration_seconds': len(audio) / 16000,
            'audio_sha256': hashlib.sha256(audio.tobytes()).hexdigest(),
            'inference_seconds': inference_seconds, 'wall_seconds': time.monotonic() - started,
            'diagnostics': str(scratch), 'segmentation': 'quiet-boundary chunks; no audio discarded',
            'language': 'English source required by this adapter; not detected',
        },
    }
    with output.open('x') as f:
        json.dump(result, f, indent=2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--handy', default='handy')
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--allow-cpu', action='store_true')
    args = parser.parse_args()
    transcribe(args.wav, args.output, args.handy, args.model, args.allow_cpu)
    print(args.output)


if __name__ == '__main__':
    main()
