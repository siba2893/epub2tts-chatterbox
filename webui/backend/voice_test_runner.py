"""Standalone runner that generates a single paragraph with Chatterbox.

Used by the FastAPI ``/api/voice-test`` endpoint to preview how an uploaded
voice sample will sound. Kept as its own script (rather than importing
chatterbox in the FastAPI process) so the heavy model load happens in an
isolated subprocess that exits cleanly afterward.

Invoke with::

    python -m webui.backend.voice_test_runner --text "..." --out test.wav \
        [--sample voice.wav] [--exaggeration 0.7] [--cfg-weight 0.4] \
        [--language en]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Paragraph to synthesize")
    parser.add_argument("--out", required=True, help="Output WAV path")
    parser.add_argument("--sample", default=None, help="Voice sample (audio_prompt_path)")
    parser.add_argument("--exaggeration", type=float, default=0.7)
    parser.add_argument("--cfg-weight", type=float, default=0.4)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    # Heavy imports deferred until after argparse so --help is fast.
    import torch
    import torchaudio as ta

    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"Attempting to use device: {device}", flush=True)

    text = args.text.strip()
    if not text:
        print("ERROR: --text was empty after stripping whitespace", file=sys.stderr)
        return 2

    if args.language != "en":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        print(f"Loading ChatterboxMultilingualTTS for language: {args.language}", flush=True)
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        if args.sample:
            wav = model.generate(text, audio_prompt_path=args.sample, language_id=args.language)
        else:
            wav = model.generate(text, language_id=args.language)
    else:
        from chatterbox.tts import ChatterboxTTS

        print("Loading ChatterboxTTS", flush=True)
        model = ChatterboxTTS.from_pretrained(device=device)
        if args.sample:
            wav = model.generate(
                text,
                audio_prompt_path=args.sample,
                exaggeration=args.exaggeration,
                cfg_weight=args.cfg_weight,
            )
        else:
            wav = model.generate(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(out_path), wav, model.sr)
    print(f"Wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
