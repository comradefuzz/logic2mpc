"""Анализ дорожки по эталону в docs/analysis.md. Вход и выход без файлов."""
from __future__ import annotations

import numpy as np

from . import cycle as cycles
from . import signal, windows
from .model import BAR, AudioRegion, Cut, MidiRegion, Occurrence, Piece, Track

EVENT_RATIO = 1.2
EVENT_MATCH = 0.97
PRE_ROLL = 0.02
COMPARE_LIMIT = 1.0
LOOP_BARS = (1, 2, 4, 8, 16)
NO_CYCLE_SCORE = 0.6
LOW_CONFIDENCE = 0.3
JOIN_GAP = BAR // 16
SHORT_REGION = 4 * BAR
SAME_REGION = 0.9
SAME_LENGTH = 0.75


def bar_of(tick: int) -> float:
    return round(tick / BAR + 1, 3)


def analyze_track(track: Track, audio: np.ndarray, sr: int, bpm: float, value: float = windows.DEFAULT) -> Cut:
    mono = audio.mean(axis=1)
    midi = any(r.notes and not r.muted for r in track.midi_regions)
    if midi:
        cut = analyze_midi(track.midi_regions, mono, sr, bpm)
    else:
        cut = analyze_audio([r for r in track.audio_regions if not r.muted], mono, sr, bpm, value)
    cut.muted_bars = sorted(
        {bar_of(r.tick) for r in track.midi_regions if r.muted} | {bar_of(r.tick) for r in track.audio_regions if r.muted}
    )
    cut.pieces = [p for p in cut.pieces if p.end > p.start]
    for piece in cut.pieces:
        piece.start_open, piece.end_open = signal.open_edges(audio, piece.start, piece.end)
    if not cut.pieces:
        cut.remark = "в экспорте нет звука"
    elif midi and any(not r.muted for r in track.audio_regions):
        cut.remark = "на дорожке есть и аудиорегионы, они не разобраны, см. AN-004"
    return cut


def join_regions(regions: list[AudioRegion]) -> tuple[list[AudioRegion], set[int]]:
    """AN-009: регионы встык на таймлайне и встык в файле это один звук."""
    joined: list[AudioRegion] = []
    merged: set[int] = set()
    for region in sorted(regions, key=lambda r: r.tick):
        last = joined[-1] if joined else None
        if (
            last and last.source is not None and last.source == region.source
            and None not in (last.offset, last.frames, region.offset, region.frames, last.length, region.length)
            and last.loop_end is None and region.loop_end is None
            and abs(last.tick + last.length - region.tick) <= JOIN_GAP
            and last.offset + last.frames == region.offset
        ):
            joined[-1] = AudioRegion(
                last.tick, None, last.length + region.length, False, last.source, last.offset, last.frames + region.frames
            )
            merged.add(last.tick)
        else:
            joined.append(region)
    return joined, merged


def same_slice(a: AudioRegion, b: AudioRegion) -> bool:
    """AN-015: один фрагмент файла или фрагмент внутри другого, если длины близки."""
    if a.source is None or a.source != b.source or None in (a.offset, a.frames, b.offset, b.frames):
        return False
    inner, outer = sorted((a, b), key=lambda r: r.frames)
    inside = outer.offset <= inner.offset and inner.offset + inner.frames <= outer.offset + outer.frames
    return inside and inner.frames >= SAME_LENGTH * outer.frames


def sounds_in_regions(regions: list[AudioRegion], merged: set[int]) -> bool:
    """AN-014: все регионы из одного файла, и каждый склеен или короток: это законченные звуки."""
    if len({r.source for r in regions}) != 1 or regions[0].source is None:
        return False
    return all(r.tick in merged or (r.length and r.length < SHORT_REGION) for r in regions)


def analyze_audio(regions: list[AudioRegion], mono: np.ndarray, sr: int, bpm: float, value: float) -> Cut:
    regions, merged = join_regions(regions)
    starts = sorted({r.tick for r in regions})
    if not starts:
        return Cut("AN-013", 0.0, [])
    looped = [r for r in regions if r.loop_end is not None]
    if len(looped) == len(regions) and all(r.length for r in regions):
        return loop_cut(regions, mono, sr, bpm)
    if not looped and len(regions) == 1:
        return whole_cut(regions[0], mono, sr, bpm)
    if not looped:
        onsets = signal.find_onsets(mono, sr)
        if len(starts) / EVENT_RATIO <= len(onsets) <= len(starts) * EVENT_RATIO:
            return event_cut(regions, mono, sr, bpm, "AN-010")
        if sounds_in_regions(regions, merged):
            return event_cut(regions, mono, sr, bpm, "AN-014")
    return window_cut(starts[0], mono, sr, bpm, value)


def whole_cut(region: AudioRegion, mono: np.ndarray, sr: int, bpm: float) -> Cut:
    """AN-011: один регион без Loop это цельный звук."""
    start = signal.ticks_to_frames(region.tick, bpm, sr)
    end = signal.sound_end(mono, start, len(mono))
    return Cut("AN-011", 1.0, [Piece(start, end, 1.0, [Occurrence(region.tick)])])


def nearest_loop(length: int) -> int:
    """Длина региона в файле это кадры исходника и бывает чуть длиннее, см. LOGIC-044."""
    return min(LOOP_BARS, key=lambda bars: abs(bars * BAR - length))


def loop_cut(regions: list[AudioRegion], mono: np.ndarray, sr: int, bpm: float) -> Cut:
    """AN-012: длина фрагмента равна длине лупа, каждый проход это вхождение."""
    bars = nearest_loop(regions[0].length)
    step = bars * BAR
    first = min(regions, key=lambda r: r.tick)
    start = signal.ticks_to_frames(first.tick, bpm, sr)
    end = signal.sound_end(mono, start, start + signal.ticks_to_frames(step, bpm, sr))
    ends = {t: r.loop_end for r in regions for t in range(r.tick, r.loop_end, step)}
    found = [Occurrence(t, length=e - t if e - t < step else None) for t, e in sorted(ends.items())]
    short = [bar_of(o.tick) for o in found if o.length]
    return Cut("AN-012", 1.0, [Piece(start, end, 1.0, found)], cycle_bars=bars, lost_bars=short)


def event_cut(regions: list[AudioRegion], mono: np.ndarray, sr: int, bpm: float, rule: str) -> Cut:
    """AN-010, AN-014: каждый регион это один звук, одинаковые сливаются по AN-015."""
    by_tick = {r.tick: r for r in sorted(regions, key=lambda r: r.tick)}
    starts = sorted(by_tick)
    frames = [signal.ticks_to_frames(t, bpm, sr) for t in starts]
    limits = frames[1:] + [len(mono)]
    pre = int(PRE_ROLL * sr)
    compare = int(COMPARE_LIMIT * sr)
    ends = [signal.sound_end(mono, s, limit) for s, limit in zip(frames, limits)]

    def slice_at(point: int, length: int) -> np.ndarray:
        begin = point - pre
        part = mono[max(0, begin) : point + length]
        return np.r_[np.zeros(max(0, -begin)), part]

    groups: list[list[int]] = []
    leaders: list[int] = []
    for index, (start, end) in enumerate(zip(frames, ends)):
        if end == start:
            continue
        for number, leader in enumerate(leaders):
            length = min(compare, end - start, ends[leader] - frames[leader])
            score, _ = signal.match(slice_at(start, length), slice_at(frames[leader], length), pre)
            same_length = min(end - start, ends[leader] - frames[leader]) >= SAME_LENGTH * max(end - start, ends[leader] - frames[leader])
            heard = same_length and signal.alike(mono[start:end], mono[frames[leader] : ends[leader]], sr)
            if same_slice(by_tick[starts[index]], by_tick[starts[leader]]) or score >= EVENT_MATCH or heard:
                groups[number].append(index)
                break
        else:
            leaders.append(index)
            groups.append([index])

    pieces = []
    lost: list[int] = []
    beat = signal.ticks_to_frames(BAR // 4, bpm, sr)
    for members in groups:
        # Образец это самый длинный звук с полным запасом перед атакой.
        clean = [i for i in members if frames[i] >= pre] or members
        leader = max(clean, key=lambda i: ends[i] - frames[i])
        begin = max(0, frames[leader] - pre)
        lead = frames[leader] - begin
        attack = mono[frames[leader] : ends[leader]]
        found = []
        for i in members:
            length = min(compare, ends[i] - frames[i], ends[leader] - frames[leader])
            score, lag = signal.match(slice_at(frames[i], length), slice_at(frames[leader], length), pre)
            if score >= EVENT_MATCH:
                hit = frames[i] + lag
                gain = signal.gain_of(mono, attack, hit)
            else:
                # Шумовой звук: волна не совпадает, сдвиг и проекция ничего не значат.
                hit = frames[i]
                gain = signal.loudness_ratio(mono[hit : ends[i]], attack)
            # Звук короче образца: нота короче, AN-033.
            short = ends[i] - frames[i] < ends[leader] - frames[leader] - beat
            length = signal.frames_to_ticks(ends[i] - frames[i], bpm, sr) if short else None
            found.append(Occurrence(signal.frames_to_ticks(hit, bpm, sr), gain, length))
            if short:
                lost.append(starts[i])
        pieces.append(Piece(begin, int(ends[leader]), 1.0, found, lead=lead))
    return Cut(rule, 1.0, pieces, lost_bars=sorted(bar_of(t) for t in lost))


def window_cut(first_tick: int, mono: np.ndarray, sr: int, bpm: float, value: float) -> Cut:
    """AN-013: окна по сетке и сравнение звука."""
    bar = signal.ticks_to_frames(BAR, bpm, sr)
    decision = windows.cut(mono, sr, signal.ticks_to_frames(first_tick, bpm, sr), bar, value)
    pieces = []
    for group in decision.groups:
        found = [Occurrence(signal.frames_to_ticks(m.position, bpm, sr)) for m in group.members]
        pieces.append(Piece(group.start, group.end, group.confidence, found))
    lost = [bar_of(signal.frames_to_ticks(p, bpm, sr)) for p in decision.uncovered]
    return Cut("AN-013", decision.confidence, pieces, cycle_bars=decision.bars, lost_bars=lost)


def analyze_midi(regions: list[MidiRegion], mono: np.ndarray, sr: int, bpm: float) -> Cut:
    audible = [r for r in regions if not r.muted]
    notes = cycles.absolute(audible)
    if not notes:
        return Cut("AN-023", 0.0, [])
    found = cycles.find_cycle(audible)
    if found is None or len(found.passes) < 2 or found.score < NO_CYCLE_SCORE:
        return region_parts(audible, mono, sr, bpm)
    size = found.bars * BAR
    beat = signal.ticks_to_frames(BAR // 4, bpm, sr)
    reach = {t: reach_of(t, size, mono, sr, bpm) for t in found.passes}
    if not any(reach.values()):
        return Cut("AN-023", 0.0, [])
    top = max(reach.values())
    whole = [t for t in found.passes if reach[t] >= top - beat]
    sample = cycles.common_pass(notes, whole, size)
    model = cycles.pass_notes(notes, sample, size)
    passes = [t for t in found.passes if reach[t]]
    others = variants(notes, found, size)
    # AN-034: точное совпадение вне сетки вытесняет проходы и варианты, с которыми пересекается.
    shifted = off_grid(notes, found.passes, model, sample, size)
    removed = [t for t in passes if t not in shifted and any(abs(t - s) < size for s in shifted)]
    passes = sorted({*(t for t in passes if t not in removed), *shifted})
    covered = [t for _, ticks in others for t in ticks if any(abs(t - x) < size for x in shifted)]
    others = [(s, [t for t in ticks if t not in covered]) for s, ticks in others]
    others = [(ticks[0], ticks) for _, ticks in others if ticks]
    reach.update({t: reach_of(t, size, mono, sr, bpm) for t in shifted})
    limit = reach[sample]
    occurrences = []
    lost = [t for t in found.passes if not reach[t]] + removed + covered
    for tick in passes:
        short = reach[tick] < limit - beat
        length = signal.frames_to_ticks(reach[tick], bpm, sr) if short else None
        occurrences.append(Occurrence(tick, length=length))
        if short:
            lost.append(tick)  # AN-033
    start = signal.ticks_to_frames(sample, bpm, sr)
    pieces = [Piece(start, start + limit, round(min(found.score, 1.0), 3), occurrences)]
    for first, ticks in others[: windows.MAX_VARIANTS - 1]:
        pieces.append(midi_piece(first, ticks, size, 1.0, mono, sr, bpm))
    lost += [t for _, ticks in others[windows.MAX_VARIANTS - 1 :] for t in ticks]
    replaced = [
        bar_of(t) for t in passes
        if t not in lost and cycles.pass_notes(notes, t, size) != model
    ]
    return Cut(
        found.source, round(min(found.score, 1.0), 3), pieces, cycle_bars=found.bars,
        lost_bars=sorted(bar_of(t) for t in set(lost)), replaced_bars=replaced,
    )


def reach_of(tick: int, size: int, mono: np.ndarray, sr: int, bpm: float) -> int:
    """Докуда в проходе дошёл звук, в кадрах от начала."""
    start = signal.ticks_to_frames(tick, bpm, sr)
    return signal.sound_end(mono, start, start + signal.ticks_to_frames(size, bpm, sr)) - start


def off_grid(
    notes: list[tuple[int, int, int]], passes: list[int], model: frozenset, sample: int, size: int
) -> list[int]:
    exact = [t for t in passes if cycles.pass_notes(notes, t, size) == model]
    first = notes[0][0] // BAR * BAR
    last = notes[-1][0]
    found = []
    for tick in range(first, last, BAR):
        if tick in passes or any(abs(tick - t) < size for t in [*exact, *found]):
            continue
        if cycles.pass_notes(notes, tick, size) == model:
            found.append(tick)
    return found


def variants(notes: list[tuple[int, int, int]], found: cycles.Cycle, size: int) -> list[tuple[int, list[int]]]:
    """Проходы вне цикла: одинаковые по нотам вместе, частые первыми."""
    grouped: dict[frozenset, list[int]] = {}
    origin = found.start % size
    ticks = sorted({(t - origin) // size * size + origin for t, _, _ in notes})
    for start in ticks:
        if start not in found.passes:
            grouped.setdefault(cycles.pass_notes(notes, start, size), []).append(start)
    return [(g[0], g) for g in sorted(grouped.values(), key=lambda g: (-len(g), g[0]))]


def midi_piece(
    start_tick: int, ticks: list[int], size: int, confidence: float, mono: np.ndarray, sr: int, bpm: float
) -> Piece:
    start = signal.ticks_to_frames(start_tick, bpm, sr)
    limit = start + signal.ticks_to_frames(size, bpm, sr)
    sample_end = max(signal.sound_end(mono, start, limit), start)
    return Piece(start, sample_end, round(confidence, 3), [Occurrence(t) for t in ticks])


def region_parts(regions: list[MidiRegion], mono: np.ndarray, sr: int, bpm: float) -> Cut:
    """AN-023: цикла нет, каждый регион это фрагмент до конца звука, одинаковые вместе."""
    filled = sorted((r for r in regions if r.notes), key=lambda r: r.tick)
    groups: list[list[MidiRegion]] = []
    for region in filled:
        kind = cycles.region_type(region)
        twin = next((g for g in groups if cycles.similarity(cycles.region_type(g[0]), kind) >= SAME_REGION), None)
        if twin:
            twin.append(region)
        else:
            groups.append([region])
    starts = sorted({r.tick for r in filled})
    pieces = []
    lost: list[float] = []
    replaced: list[float] = []
    for number, group in enumerate(sorted(groups, key=lambda g: (-len(g), g[0].tick))):
        if number >= windows.MAX_VARIANTS:
            lost += [bar_of(r.tick) for r in group]
            continue
        tick = group[0].tick
        # Нота может лежать раньше начала региона, см. LOGIC-063: фрагмент начинается с неё.
        begin = min(tick, tick + min(n.tick for n in group[0].notes))
        begin = begin // BAR * BAR if begin < tick else tick
        start = signal.ticks_to_frames(begin, bpm, sr)
        model = cycles.region_type(group[0])
        replaced += [bar_of(r.tick) for r in group[1:] if cycles.region_type(r) != model]
        following = [t for t in starts if t > tick]
        limit = signal.ticks_to_frames(following[0], bpm, sr) if following else len(mono)
        end = signal.sound_end(mono, start, limit)
        found = [Occurrence(r.tick - (tick - begin)) for r in group]
        pieces.append(Piece(start, end, LOW_CONFIDENCE, found))
    return Cut("AN-023", LOW_CONFIDENCE, pieces, lost_bars=sorted(lost), replaced_bars=sorted(replaced))
