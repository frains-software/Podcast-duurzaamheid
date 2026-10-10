"""Opdrachtregel van de Grondstof-studio.

    python -m studio validate [DATUM]     controleer een redactiescript
    python -m studio plan                 bepaal wat de geplande run moet doen (voor GitHub Actions)
    python -m studio write [DATUM]        terugvaloptie: laat Claude zelf een script schrijven
    python -m studio produce [DATUM]      maak audio met ElevenLabs en schrijf de afleveringsdata
    python -m studio window               toon de afleveringen die gepubliceerd blijven
    python -m studio site                 bouw website, episodes.json en RSS-feed in _site/
    python -m studio assets               (her)genereer tunes, cover en app-icoon
    python -m studio promo-voice SPEC     spreek een promovideo in
    python -m studio promo-video SPEC     render een promovideo (MP4 + SRT)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from . import config
from .script import fmt_duration, parse


def _day(value: str | None) -> str:
    if not value or value == "today":
        return config.today_local().isoformat()
    return date.fromisoformat(value).isoformat()


def cmd_validate(args) -> int:
    day = _day(args.date)
    path = config.script_path(day)
    if not path.exists():
        print(f"✗ {path.relative_to(config.ROOT)} bestaat niet")
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"✗ FOUT: ongeldige JSON: {exc}")
        return 1
    script, errors, warnings = parse(data, expected_date=day)
    for e in errors:
        print(f"✗ FOUT: {e}")
    for w in warnings:
        print(f"! waarschuwing: {w}")
    if errors:
        return 1
    stories = sum(1 for s in script.segments if s.kind == "story")
    print(
        f"✓ {day}: '{script.title}': {stories} berichten, {script.words} woorden, "
        f"geschat {fmt_duration(script.estimated_seconds)}"
    )
    return 0


def cmd_plan(args) -> int:
    """Beslislogica voor de workflow. Schrijft key=value naar $GITHUB_OUTPUT."""
    from .plan import decide

    result = decide(event=args.event, requested_date=args.date, force=args.force, changed=args.changed)
    lines = [f"{k}={v}" for k, v in result.items()]
    print("\n".join(lines))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return 0


def cmd_write(args) -> int:
    from .writer import write_script

    day = _day(args.date)
    path = write_script(day)
    print(f"✓ script geschreven: {path.relative_to(config.ROOT)}")
    return cmd_validate(argparse.Namespace(date=day))


def cmd_produce(args) -> int:
    from .produce import produce

    day = _day(args.date)
    meta = produce(day, fake_voice=args.fake_voice)
    print(f"✓ aflevering {day} klaar: {fmt_duration(meta['duration'])}, {meta['size'] / 1e6:.1f} MB")
    return 0


def cmd_window(args) -> int:
    from .site import window

    for meta in window():
        print(meta["id"])
    return 0


def cmd_site(args) -> int:
    from .site import build_site

    out = build_site(audio_dir=args.audio_dir)
    print(f"✓ website gebouwd in {out}")
    return 0


def cmd_assets(args) -> int:
    from .art import render_all as render_art
    from .jingle import render_all as render_jingles

    for p in render_jingles():
        print(f"♪ {p.relative_to(config.ROOT)}")
    for p in render_art():
        print(f"▣ {p.relative_to(config.ROOT)}")
    return 0


def cmd_promo_voice(args) -> int:
    from pathlib import Path

    from .promo import voice

    voice(Path(args.spec), fake=args.fake_voice)
    return 0


def cmd_promo_video(args) -> int:
    from pathlib import Path

    from .promo import render

    render(Path(args.spec), Path(args.out) if args.out else None)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studio", description="Grondstof-studio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="controleer een redactiescript")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("plan", help="bepaal de actie voor de geplande run")
    p.add_argument("--event", default="workflow_dispatch")
    p.add_argument("--date", default="")
    p.add_argument("--force", default="false")
    p.add_argument("--changed", default="", help="gewijzigde bestanden (spatie-gescheiden)")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("write", help="schrijf een script met Claude (terugvaloptie)")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("produce", help="maak de audio en afleveringsdata")
    p.add_argument("date", nargs="?")
    p.add_argument("--fake-voice", action="store_true", help="testmodus zonder ElevenLabs")
    p.set_defaults(func=cmd_produce)

    p = sub.add_parser("window", help="afleveringen die gepubliceerd blijven")
    p.set_defaults(func=cmd_window)

    p = sub.add_parser("site", help="bouw website en feed")
    p.add_argument("--audio-dir", default=None)
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("assets", help="genereer tunes en beeld")
    p.set_defaults(func=cmd_assets)

    p = sub.add_parser("promo-voice", help="spreek een promovideo in")
    p.add_argument("spec")
    p.add_argument("--fake-voice", action="store_true")
    p.set_defaults(func=cmd_promo_voice)

    p = sub.add_parser("promo-video", help="render een promovideo")
    p.add_argument("spec")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_promo_video)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
