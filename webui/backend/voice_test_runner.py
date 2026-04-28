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
    parser.add_argument(
        "--engine",
        choices=["chatterbox", "xtts_v2"],
        default="chatterbox",
        help="TTS engine to use for the preview.",
    )
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
    print(f"Attempting to use device: {device} | engine: {args.engine}", flush=True)

    text = args.text.strip()
    if not text:
        print("ERROR: --text was empty after stripping whitespace", file=sys.stderr)
        return 2

    if args.engine == "xtts_v2":
        try:
            from TTS.api import TTS
        except ImportError:
            print(
                "ERROR: engine 'xtts_v2' requires the Coqui TTS package. "
                "Install with: pip install TTS",
                file=sys.stderr,
            )
            return 3
        if not args.sample:
            print("ERROR: xtts_v2 requires --sample (a voice to clone)", file=sys.stderr)
            return 4
        print("Loading XTTS v2", flush=True)
        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        wav = model.tts(text=text, speaker_wav=args.sample, language=args.language)
        sr = 24000
    elif args.language != "en":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        print(f"Loading ChatterboxMultilingualTTS for language: {args.language}", flush=True)
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        if args.sample:
            wav = model.generate(text, audio_prompt_path=args.sample, language_id=args.language)
        else:
            wav = model.generate(text, language_id=args.language)
        sr = model.sr
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
        sr = model.sr

    if not isinstance(wav, torch.Tensor):
        wav = torch.tensor(wav, dtype=torch.float32).unsqueeze(0)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(out_path), wav, sr)
    print(f"Wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
