"""Bouwt de publieke site: RSS-feed (Spotify/Apple), JSON voor de app, transcripties en webspeler."""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from . import config

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def window() -> list[dict]:
    """De afleveringen die in feed en app staan: de nieuwste N, nieuwste eerst."""
    keep = int(config.schedule().get("keep_episodes", 90))
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(config.EPISODES.glob("*.json"), reverse=True)]
    return metas[:keep]


def build_site(audio_dir: str | None = None, out: Path | None = None) -> Path:
    out = out or config.ROOT / "_site"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(config.SITE_SRC, out)
    (out / "episodes").mkdir(exist_ok=True)
    (out / "transcripts").mkdir(exist_ok=True)
    (out / "chapters").mkdir(exist_ok=True)
    (out / "audio").mkdir(exist_ok=True)
    art = config.ASSETS / "art"
    for name in ("cover-3000.jpg", "cover-1400.jpg", "cover-600.jpg", "favicon.png", "app-icon-1024.png"):
        shutil.copy2(art / name, out / name)
    _app_icons(art / "app-icon-1024.png", out)
    sw = out / "sw.js"
    sw.write_text(sw.read_text().replace("__BUILD__", datetime.now(config.tz()).strftime("%Y%m%d%H%M%S")))

    episodes = window()
    src_audio = Path(audio_dir) if audio_dir else config.BUILD / "audio"
    for meta in episodes:
        mp3 = src_audio / f"{meta['id']}.mp3"
        if mp3.exists():
            shutil.copy2(mp3, out / "audio" / mp3.name)
        else:
            print(f"! audio ontbreekt voor {meta['id']} ({mp3})")
        detail = dict(meta, audioUrl=_url(meta["audioFile"]))
        (out / "episodes" / f"{meta['id']}.json").write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8")
        (out / "transcripts" / f"{meta['id']}.vtt").write_text(_vtt(meta), encoding="utf-8")
        (out / "chapters" / f"{meta['id']}.json").write_text(json.dumps(_chapters(meta), ensure_ascii=False), encoding="utf-8")

    (out / "episodes.json").write_text(json.dumps(_index(episodes), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "feed.xml").write_bytes(_feed(episodes))
    (out / ".nojekyll").write_text("")
    return out


def _app_icons(source: Path, out: Path) -> None:
    """Iconen voor 'Zet op beginscherm' (iOS) en de web-app-manifest."""
    from PIL import Image

    icon = Image.open(source).convert("RGB")
    for name, px in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        icon.resize((px, px), Image.Resampling.LANCZOS).save(out / name, optimize=True)


def _url(path: str) -> str:
    return f"{config.site_url()}/{path.lstrip('/')}"


def _show_block() -> dict:
    show = config.show()
    return {
        "title": show["title"],
        "subtitle": show["subtitle"],
        "tagline": show["tagline"],
        "description": show["description"],
        "host": show["host"],
        "hostRole": show["host_role"],
        "organisation": show["organisation"],
        "linkedinUrl": show.get("linkedin_url") or None,
        "companies": show["companies"],
        "cover": _url("cover-1400.jpg"),
        "feedUrl": _url("feed.xml"),
        "website": config.site_url() + "/",
        "spotifyUrl": show.get("spotify_url") or None,
        "appleUrl": show.get("apple_url") or None,
        "publishTime": config.schedule()["publish_time"],
        "timezone": config.schedule()["timezone"],
    }


def _index(episodes: list[dict]) -> dict:
    """Lichte index voor de app; details (transcript, golfvorm) staan per aflevering apart."""
    items = []
    for m in episodes:
        items.append({
            "id": m["id"],
            "number": m["number"],
            "date": m["date"],
            "published": m["published"],
            "title": m["title"],
            "summary": m["summary"],
            "duration": m["duration"],
            "audioUrl": _url(m["audioFile"]),
            "detailUrl": _url(f"episodes/{m['id']}.json"),
            "headlines": [c["title"] for c in m["chapters"] if c["kind"] == "story"],
            "numberOfTheDay": m.get("numberOfTheDay"),
        })
    return {"generated": datetime.now(config.tz()).isoformat(timespec="seconds"), "show": _show_block(), "episodes": items}


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _vtt(meta: dict) -> str:
    lines = ["WEBVTT", ""]
    for i, cue in enumerate(meta["transcript"], 1):
        lines += [str(i), f"{_ts(cue['start'])} --> {_ts(cue['end'])}", f"<v {config.show()['host']}>{cue['text']}", ""]
    return "\n".join(lines)


def _chapters(meta: dict) -> dict:
    """Podcasting 2.0 JSON-hoofdstukken."""
    return {
        "version": "1.2.0",
        "chapters": [
            {"startTime": c["start"], "title": c["title"], **({"url": c["sources"][0]["url"]} if c["sources"] else {})}
            for c in meta["chapters"]
        ],
    }


def _shownotes(meta: dict) -> str:
    parts = [f"<p>{html.escape(meta['summary'])}</p>"]
    stories = [c for c in meta["chapters"] if c["kind"] == "story"]
    if stories:
        parts.append("<p><strong>In deze aflevering</strong></p><ul>")
        for c in stories:
            mins, secs = divmod(int(c["start"]), 60)
            parts.append(f"<li>({mins:02d}:{secs:02d}) {html.escape(c['title'])}</li>")
        parts.append("</ul>")
    if meta.get("sources"):
        parts.append("<p><strong>Bronnen</strong></p><ul>")
        for s in meta["sources"]:
            label = " — ".join(x for x in (s.get("publisher"), s.get("title")) if x)
            parts.append(f'<li><a href="{html.escape(s["url"])}">{html.escape(label or s["url"])}</a></li>')
        parts.append("</ul>")
    show = config.show()
    parts.append(f"<p>{html.escape(show['title'])}: {html.escape(show['tagline'].lower())}. "
                 f"Elke ochtend om {config.schedule()['publish_time']} een nieuwe aflevering.</p>")
    if show.get("linkedin_url"):
        parts.append(f'<p>Gemaakt door <a href="{html.escape(show["linkedin_url"])}">{html.escape(show["host"])}</a>.</p>')
    return "".join(parts)


def _plain(meta: dict) -> str:
    lines = [meta["summary"], ""]
    for c in meta["chapters"]:
        if c["kind"] == "story":
            lines.append(f"• {c['title']}")
    return "\n".join(lines)


def _feed(episodes: list[dict]) -> bytes:
    show = config.show()
    it, pc, atom = NS["itunes"], NS["podcast"], NS["atom"]
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")

    def sub(parent, tag, text=None, **attrs):
        el = ET.SubElement(parent, tag, {k.replace("__", ":"): str(v) for k, v in attrs.items()})
        if text is not None:
            el.text = str(text)
        return el

    sub(ch, "title", show["title"])
    sub(ch, "link", config.site_url() + "/")
    sub(ch, "language", show["language"])
    sub(ch, "copyright", show["copyright"])
    sub(ch, "description", show["description"])
    sub(ch, f"{{{atom}}}link", href=_url("feed.xml"), rel="self", type="application/rss+xml")
    sub(ch, "generator", "Grondstof studio")
    if episodes:
        sub(ch, "lastBuildDate", format_datetime(datetime.fromisoformat(episodes[0]["published"])))
    image = sub(ch, "image")
    sub(image, "url", _url("cover-1400.jpg"))
    sub(image, "title", show["title"])
    sub(image, "link", config.site_url() + "/")

    sub(ch, f"{{{it}}}author", f"{show['host']} · {show['organisation']}")
    sub(ch, f"{{{it}}}subtitle", show["subtitle"])
    sub(ch, f"{{{it}}}summary", show["description"])
    sub(ch, f"{{{it}}}type", "episodic")
    sub(ch, f"{{{it}}}explicit", "true" if show.get("explicit") else "false")
    sub(ch, f"{{{it}}}image", href=_url("cover-3000.jpg"))
    owner = sub(ch, f"{{{it}}}owner")
    sub(owner, f"{{{it}}}name", show["owner_name"])
    if show.get("owner_email"):
        sub(owner, f"{{{it}}}email", show["owner_email"])
    cat = ET.SubElement(ch, f"{{{it}}}category", {"text": show["category"]})
    if show.get("subcategory"):
        ET.SubElement(cat, f"{{{it}}}category", {"text": show["subcategory"]})
    if show.get("category2"):
        ET.SubElement(ch, f"{{{it}}}category", {"text": show["category2"]})
    sub(ch, f"{{{pc}}}guid", _podcast_guid())
    sub(ch, f"{{{pc}}}medium", "podcast")
    person = {"role": "host"}
    if show.get("linkedin_url"):
        person["href"] = show["linkedin_url"]
    sub(ch, f"{{{pc}}}person", show["host"], **person)

    for m in episodes:
        item = sub(ch, "item")
        sub(item, "title", m["title"])
        sub(item, "description", _plain(m))
        sub(item, f"{{{NS['content']}}}encoded", _shownotes(m))
        sub(item, "link", f"{config.site_url()}/#{m['id']}")
        sub(item, "guid", f"grondstof-{m['id']}", isPermaLink="false")
        sub(item, "pubDate", format_datetime(datetime.fromisoformat(m["published"])))
        sub(item, "enclosure", url=_url(m["audioFile"]), length=m["size"], type="audio/mpeg")
        sub(item, f"{{{it}}}duration", int(round(m["duration"])))
        sub(item, f"{{{it}}}episode", m["number"])
        sub(item, f"{{{it}}}episodeType", "full")
        sub(item, f"{{{it}}}explicit", "false")
        sub(item, f"{{{it}}}image", href=_url("cover-3000.jpg"))
        sub(item, f"{{{pc}}}transcript", url=_url(f"transcripts/{m['id']}.vtt"), type="text/vtt", language="nl")
        sub(item, f"{{{pc}}}chapters", url=_url(f"chapters/{m['id']}.json"), type="application/json+chapters")

    ET.indent(rss, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="utf-8")


def _podcast_guid() -> str:
    """Stabiele Podcasting 2.0-GUID (UUIDv5 van de feed-URL zonder protocol)."""
    import uuid

    feed = _url("feed.xml").split("://", 1)[-1].rstrip("/")
    return str(uuid.uuid5(uuid.UUID("ead4c236-bf58-58c6-a2c6-a6b28d128cb6"), feed))
