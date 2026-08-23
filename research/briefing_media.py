#!/usr/bin/env python3
"""
Prepare one Monday Briefing edition's media for delivery.

    python3 research/briefing_media.py "<source.mp4>" <edition-slug> [poster-seconds]

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
"""

from __future__ import annotations

import json
import pathlib
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


def audio_md5(path: pathlib.Path) -> str:
    """md5 of the DEMUXED audio stream - unchanged iff it was copied, not re-encoded."""
    r = run([FFMPEG, '-v', 'error', '-i', str(path), '-map', '0:a', '-c', 'copy',
             '-f', 'md5', '-'])
    if r.returncode != 0:
        raise SystemExit(f'could not hash the audio of {path}:\n{r.stderr}')
    return r.stdout.strip()


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    src = pathlib.Path(sys.argv[1])
    slug = sys.argv[2]
    poster_at = sys.argv[3] if len(sys.argv) > 3 else '0.6'
    if not src.exists():
        print(f'  source not found: {src}')
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    video_out = OUT / f'astrid-{slug}.mp4'
    poster_out = OUT / f'astrid-{slug}.jpg'

    before = probe(src)
    print(f'  source   {before["w"]}x{before["h"]}  {before["duration"]:.3f}s  '
          f'{before["size"]/1048576:.1f} MB  {before["bitrate"]/1000:.0f} kbit/s  '
          f'{before["vcodec"]}/{before["acodec"]}')

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
    print(f'\n  upload with:')
    print(f'    vercel blob put {video_out} --pathname research/briefing/{video_out.name} --allow-overwrite')
    print(f'    vercel blob put {poster_out} --pathname research/briefing/{poster_out.name} --allow-overwrite')
    print('  target store_TDKaAvtl8194sGs0 explicitly - two stores are connected.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
