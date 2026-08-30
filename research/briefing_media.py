#!/usr/bin/env python3
"""
Prepare one Monday Briefing edition's media for delivery.

    python3 research/briefing_media.py "<source.mp4>" <slug> <locale> [--presenter=NAME] [--poster=SEC]

WHY THIS EXISTS. Astrid's recordings arrive at a mastering bitrate. The
24 August edition was 206 MB at 9.8 Mbit/s for 2:53 - a viewer on mobile would
need a sustained 9 Mbit/s to watch it without stalling, which most will not
have. 05-ROUTE-AND-INTEGRATION leaves delivery to production and the media rule
permits transcoding "only if production delivery genuinely requires it and the
result is visually and audibly indistinguishable".

THE AUDIO IS NEVER RE-ENCODED, and that is the whole point of doing this with
ffmpeg rather than with macOS avconvert. The design lock forbids muting,
redubbing, replacing or reinterpreting Astrid's recording, and a second AAC
generation is a reinterpretation however small. `-c:a copy` moves the original
AAC stream across untouched, and this script PROVES it did: it hashes the
decoded audio stream of the source and of the output and refuses to continue if
they differ. That is a claim you can check rather than a promise.

    audio      copied, bit-for-bit, verified by md5 of the demuxed stream
    video      re-encoded H.264 at CRF, same resolution and frame rate
    original   never modified. It stays wherever it was delivered and its
               sha256 is recorded in research/briefings.json.

WHY CRF AND NOT A TARGET SIZE. A fixed bitrate spends the same bits on a static
head-and-shoulders shot as on motion. CRF holds quality constant and lets the
file be whatever size that needs, which for this material is small.

WHY NOT 720p. The stage is 400x510 on desktop and up to 570px tall on mobile,
so the portrait renders about 287x510 and 321x570. At 3x device pixel ratio the
mobile case wants close to 1080x1920, which is what the source already is.
Downscaling would be visible on the phones most of this audience uses.

WHY PORTRAIT IS REFUSED OUTRIGHT. Added 30 August 2026 on GPT's ruling, after a
landscape 1280x720 recording was delivered for edition 002 and NOTHING in the
pipeline would have stopped it. This script checked duration, resolution
stability and audio identity; build_check.py never looks at the video at all.
The edition would have deployed and the first anyone would have known was seeing
it live.

The stage is portrait at every breakpoint - 400x510, 330x470, and full width by
min(124vw, 570px) - and the player is object-fit: contain, which is itself part
of the design lock. A 16:9 file in that box renders as a band across the middle
with 55-60% of the stage empty, and the topline and play control, which are
pinned to the stage edges, end up over background rather than over the
presenter. There is no encode that fixes it: it is the wrong shape, not the
wrong bitrate.

So the shape is now a gate here AND recorded into research/briefings.json as
video.width / video.height, which gen_briefing.py and build_check.py refuse on.
The deploy gate cannot run ffprobe - Vercel builds it with python alone - so the
measurement is taken once, here, and carried in the data.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'research' / '.media'
FFMPEG = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
FFPROBE = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'

# Visually indistinguishable for a talking head at this resolution. Raise the
# number to make the file smaller, and check the result before shipping it.
CRF = '23'

DATA = ROOT / 'research' / 'briefings.json'

# The locales the Monday Briefing publishes in. GPT's ruling of 30 Aug 2026:
# the unprefixed route is always English, /es/ is always Spanish.
LOCALES = ('en', 'es')

# What the mobile stage wants at 3x. Not a refusal - the refusal is the shape.
PREFERRED_W, PREFERRED_H = 1080, 1920


def slugify(name: str) -> str:
    """Presenter name to a filename part: 'Bianca' -> 'bianca'."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(path: pathlib.Path) -> dict:
    r = run([FFPROBE, '-v', 'error', '-print_format', 'json',
             '-show_format', '-show_streams', str(path)])
    if r.returncode != 0:
        raise SystemExit(f'ffprobe failed on {path}:\n{r.stderr}')
    d = json.loads(r.stdout)
    v = next(s for s in d['streams'] if s['codec_type'] == 'video')
    a = next((s for s in d['streams'] if s['codec_type'] == 'audio'), None)
    return {
        'duration': float(d['format']['duration']),
        'size': int(d['format']['size']),
        'bitrate': int(d['format'].get('bit_rate', 0)),
        'w': v['width'], 'h': v['height'],
        'vcodec': v['codec_name'],
        'fps': v.get('r_frame_rate'),
        'acodec': a['codec_name'] if a else None,
        'arate': a.get('sample_rate') if a else None,
        'achannels': a.get('channels') if a else None,
    }


def sha256(path: pathlib.Path) -> str:
    """Of the ORIGINAL delivery, so the master this edition came from is named
    in the record and a re-delivery cannot be mistaken for the same file."""
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def audio_md5(path: pathlib.Path) -> str:
    """md5 of the DEMUXED audio stream - unchanged iff it was copied, not re-encoded."""
    r = run([FFMPEG, '-v', 'error', '-i', str(path), '-map', '0:a', '-c', 'copy',
             '-f', 'md5', '-'])
    if r.returncode != 0:
        raise SystemExit(f'could not hash the audio of {path}:\n{r.stderr}')
    return r.stdout.strip()


def presenter_from_data(slug: str, locale: str) -> str | None:
    """The presenter recorded for this edition, so the filename cannot drift
    from research/briefings.json by a typo on the command line."""
    if not DATA.exists():
        return None
    doc = json.loads(DATA.read_text(encoding='utf-8'))
    for ed in doc.get('editions', []):
        if ed.get('slug') == slug and (ed.get('locale') or 'en') == locale:
            return ((ed.get('video') or {}).get('presenter') or '').strip() or None
    return None


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__.strip().splitlines()[2])
        return 2
    src = pathlib.Path(sys.argv[1])
    slug = sys.argv[2]
    locale = sys.argv[3].strip().lower()
    poster_at = '0.6'
    presenter = None
    for a in sys.argv[4:]:
        if a.startswith('--poster='):
            poster_at = a.split('=', 1)[1]
        elif a.startswith('--presenter='):
            presenter = a.split('=', 1)[1].strip()
        else:
            print(f'  unknown argument: {a}')
            return 2

    if locale not in LOCALES:
        print(f'  locale must be one of {", ".join(sorted(LOCALES))}, got {locale!r}')
        return 2
    if not src.exists():
        print(f'  source not found: {src}')
        return 1

    presenter = presenter or presenter_from_data(slug, locale)
    if not presenter:
        print(f'  no presenter recorded for {locale}/{slug} in research/briefings.json, '
              f'and none given. Pass --presenter=NAME.')
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    # LOCALE IS PART OF THE FILENAME. GPT's ruling of 30 Aug 2026: edition
    # identity is locale plus publication date, and media filenames carry it.
    # The English and Spanish recordings of one Monday are two different files
    # and must never resolve to the same path.
    stem = f'{slugify(presenter)}-{slug}-{locale}'
    video_out = OUT / f'{stem}.mp4'
    poster_out = OUT / f'{stem}.jpg'

    before = probe(src)
    print(f'  source   {before["w"]}x{before["h"]}  {before["duration"]:.3f}s  '
          f'{before["size"]/1048576:.1f} MB  {before["bitrate"]/1000:.0f} kbit/s  '
          f'{before["vcodec"]}/{before["acodec"]}')

    # THE SHAPE GATE. Refused before the encode, not after, because the encode
    # is slow and the answer cannot change.
    if before['h'] <= before['w']:
        shape = 'square' if before['h'] == before['w'] else 'landscape'
        print(f'\n  REFUSED - the briefing stage is portrait and this recording is {shape}.')
        print(f'    delivered   {before["w"]}x{before["h"]}')
        print(f'    required    portrait, height greater than width, {PREFERRED_W}x{PREFERRED_H} preferred')
        print( '    why         the stage is 400x510, 330x470 and full width by min(124vw, 570px),')
        print( '                with object-fit: contain locked. A landscape file renders as a band')
        print( '                across the middle with 55-60% of the stage empty, and the topline')
        print( '                and play control sit over background instead of the presenter.')
        print( '    fix         re-export portrait from the same recording. No encode setting')
        print( '                changes the shape, and the stage is design-frozen.')
        return 1

    if before['h'] < PREFERRED_H or before['w'] < PREFERRED_W:
        print(f'  note     {before["w"]}x{before["h"]} is portrait but below {PREFERRED_W}x{PREFERRED_H}. '
              f'The mobile stage is up to 570px tall, so at 3x it wants ~{PREFERRED_W}x{PREFERRED_H}; '
              'this will look soft on the phones most of this audience uses.')

    print('  encoding video, copying audio...')
    r = run([FFMPEG, '-y', '-v', 'error', '-i', str(src),
             '-c:v', 'libx264', '-crf', CRF, '-preset', 'slow',
             '-profile:v', 'high', '-pix_fmt', 'yuv420p',
             '-c:a', 'copy',                 # NEVER re-encode Astrid
             '-movflags', '+faststart',      # metadata first, so it streams
             str(video_out)])
    if r.returncode != 0:
        print(r.stderr)
        return 1

    after = probe(video_out)
    print(f'  output   {after["w"]}x{after["h"]}  {after["duration"]:.3f}s  '
          f'{after["size"]/1048576:.1f} MB  {after["bitrate"]/1000:.0f} kbit/s  '
          f'{after["vcodec"]}/{after["acodec"]}')

    problems = []
    if abs(after['duration'] - before['duration']) > 0.05:
        problems.append(f'duration moved: {before["duration"]:.3f} -> {after["duration"]:.3f}')
    if (after['w'], after['h']) != (before['w'], before['h']):
        problems.append(f'resolution changed: {before["w"]}x{before["h"]} -> {after["w"]}x{after["h"]}')
    if after['acodec'] != before['acodec'] or after['arate'] != before['arate'] \
            or after['achannels'] != before['achannels']:
        problems.append(f'audio format changed: {before["acodec"]}/{before["arate"]}/'
                        f'{before["achannels"]} -> {after["acodec"]}/{after["arate"]}/{after["achannels"]}')

    src_a, out_a = audio_md5(src), audio_md5(video_out)
    if src_a != out_a:
        problems.append(f'AUDIO STREAM IS NOT IDENTICAL\n      source {src_a}\n      output {out_a}')
    else:
        print(f'  audio    bit-for-bit identical  ({src_a.split("=")[-1][:16]}...)')

    if problems:
        print('\n  REFUSED - the delivery file is not the same recording:')
        for p in problems:
            print(f'    {p}')
        video_out.unlink(missing_ok=True)
        return 1

    r = run([FFMPEG, '-y', '-v', 'error', '-ss', poster_at, '-i', str(src),
             '-frames:v', '1', '-q:v', '2', str(poster_out)])
    if r.returncode != 0:
        print(r.stderr)
        return 1
    print(f'  poster   {poster_out.name} at {poster_at}s  '
          f'{poster_out.stat().st_size/1024:.0f} KB')

    saved = (1 - after['size'] / before['size']) * 100
    print(f'\n  {before["size"]/1048576:.1f} MB -> {after["size"]/1048576:.1f} MB  '
          f'({saved:.0f}% smaller), audio untouched, {after["duration"]:.2f}s')

    # THE MEASUREMENTS THE EDITION DATA NEEDS, in the shape it needs them.
    # durationSeconds, width and height are measured here and never typed: the
    # deploy gate has no ffprobe and refuses an edition whose recorded shape is
    # not portrait, so these three fields are what carries the evidence forward.
    block = {
        'src': f'/media/briefing/{video_out.name}',
        'poster': f'/media/briefing/{poster_out.name}',
        'durationSeconds': round(after['duration'], 3),
        'width': after['w'],
        'height': after['h'],
        'presenter': presenter,
        'sourceFile': src.name,
        'sourceSha256': sha256(src),
        'posterFrameSeconds': float(poster_at),
        'deliverySize': (f'{after["size"]/1048576:.1f} MB at {after["bitrate"]/1000:.0f} kbit/s, '
                         f'{after["w"]}x{after["h"]}, audio copied from the master'),
    }
    print('\n  install the delivery files:')
    print(f'    cp {video_out} media/briefing/{video_out.name}')
    print(f'    cp {poster_out} media/briefing/{poster_out.name}')
    print('  (edition 001 is served from the repo at /media/briefing/, not from blob.')
    print('   If this ever moves to blob storage, target store_TDKaAvtl8194sGs0')
    print('   explicitly - two stores are connected and the default is the other one.)')
    print(f'\n  then set editions[{locale}/{slug}].video in research/briefings.json to:\n')
    for line in json.dumps(block, indent=2, ensure_ascii=False).splitlines():
        print(f'    {line}')
    print('\n  markers and transcript are NOT measured here. Somebody still has to listen.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
