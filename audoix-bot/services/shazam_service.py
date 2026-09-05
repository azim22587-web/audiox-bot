import asyncio
import io
import math
import os
import subprocess
import time
import uuid
import logging
from binascii import crc32
from base64 import b64encode
from ctypes import LittleEndianStructure, c_uint32
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import aiohttp
from config import FFMPEG_PATH

logger = logging.getLogger(__name__)

DATA_URI_PREFIX = "data:audio/vnd.shazam.sig;base64,"
HANNING_MATRIX = np.hanning(2050)[1:-1]

class SampleRate(IntEnum):
    _8000 = 1
    _11025 = 2
    _16000 = 3
    _32000 = 4
    _44100 = 5
    _48000 = 6

class FrequencyBand(IntEnum):
    hz_0_250 = -1
    hz_250_520 = 0
    hz_520_1450 = 1
    hz_1450_3500 = 2
    hz_3500_5500 = 3

class RawSignatureHeader(LittleEndianStructure):
    _pack_ = True
    _fields_ = [
        ("magic1", c_uint32),
        ("crc32", c_uint32),
        ("size_minus_header", c_uint32),
        ("magic2", c_uint32),
        ("void1", c_uint32 * 3),
        ("shifted_sample_rate_id", c_uint32),
        ("void2", c_uint32 * 2),
        ("number_samples_plus_divided_sample_rate", c_uint32),
        ("fixed_value", c_uint32),
    ]

class FrequencyPeak:
    def __init__(self, fft_pass_number: int, peak_magnitude: int, corrected_peak_frequency_bin: int, sample_rate_hz: int = 16000):
        self.fft_pass_number = fft_pass_number
        self.peak_magnitude = peak_magnitude
        self.corrected_peak_frequency_bin = corrected_peak_frequency_bin
        self.sample_rate_hz = sample_rate_hz

class DecodedMessage:
    def __init__(self):
        self.sample_rate_hz = 16000
        self.number_samples = 0
        self.frequency_band_to_sound_peaks: Dict[FrequencyBand, List[FrequencyPeak]] = {}

    def encode_to_binary(self) -> bytes:
        header = RawSignatureHeader()
        header.magic1 = 0xCAFE2580
        header.magic2 = 0x94119C00
        header.shifted_sample_rate_id = int(getattr(SampleRate, f"_{self.sample_rate_hz}")) << 27
        header.fixed_value = (15 << 19) + 0x40000
        header.number_samples_plus_divided_sample_rate = int(self.number_samples + self.sample_rate_hz * 0.24)

        contents_buf = io.BytesIO()
        for frequency_band, frequency_peaks in sorted(self.frequency_band_to_sound_peaks.items()):
            peaks_buf = io.BytesIO()
            fft_pass_number = 0
            for frequency_peak in frequency_peaks:
                if frequency_peak.fft_pass_number < fft_pass_number:
                    continue
                if frequency_peak.fft_pass_number - fft_pass_number >= 255:
                    peaks_buf.write(b"\xff")
                    peaks_buf.write(frequency_peak.fft_pass_number.to_bytes(4, "little"))
                    fft_pass_number = frequency_peak.fft_pass_number

                peaks_buf.write(bytes([frequency_peak.fft_pass_number - fft_pass_number]))
                peaks_buf.write(frequency_peak.peak_magnitude.to_bytes(2, "little"))
                peaks_buf.write(frequency_peak.corrected_peak_frequency_bin.to_bytes(2, "little"))
                fft_pass_number = frequency_peak.fft_pass_number

            contents_buf.write((0x60030040 + int(frequency_band)).to_bytes(4, "little"))
            contents_buf.write(len(peaks_buf.getvalue()).to_bytes(4, "little"))
            contents_buf.write(peaks_buf.getvalue())
            contents_buf.write(b"\x00" * (-len(peaks_buf.getvalue()) % 4))

        header.size_minus_header = len(contents_buf.getvalue()) + 8
        buf = io.BytesIO()
        buf.write(header)
        buf.write((0x40000000).to_bytes(4, "little"))
        buf.write((len(contents_buf.getvalue()) + 8).to_bytes(4, "little"))
        buf.write(contents_buf.getvalue())

        buf.seek(8)
        header.crc32 = crc32(buf.read()) & 0xFFFFFFFF
        buf.seek(0)
        buf.write(header)
        return buf.getvalue()

    def encode_to_uri(self) -> str:
        return DATA_URI_PREFIX + b64encode(self.encode_to_binary()).decode("ascii")

class RingBuffer(list):
    def __init__(self, buffer_size: int, default_value=None):
        if default_value is not None:
            list.__init__(self, [default_value] * buffer_size)
        else:
            list.__init__(self, [None] * buffer_size)
        self.position = 0
        self.buffer_size = buffer_size
        self.num_written = 0

    def append(self, value):
        self[self.position] = value
        self.position = (self.position + 1) % self.buffer_size
        self.num_written += 1

class SignatureGenerator:
    def __init__(self):
        self.input_pending_processing: List[int] = []
        self.samples_processed = 0
        self.ring_buffer_of_samples = RingBuffer(buffer_size=2048, default_value=0)
        self.fft_outputs = RingBuffer(buffer_size=256, default_value=[0.0] * 1025)
        self.spread_fft_output = RingBuffer(buffer_size=256, default_value=[0.0] * 1025)
        self.MAX_TIME_SECONDS = 12.0
        self.MAX_PEAKS = 255
        self.next_signature = DecodedMessage()

    def feed_input(self, s16le_mono_samples: List[int]):
        self.input_pending_processing.extend(s16le_mono_samples)

    def get_next_signature(self) -> Optional[DecodedMessage]:
        if len(self.input_pending_processing) - self.samples_processed < 128:
            return None
        while len(self.input_pending_processing) - self.samples_processed >= 128 and (
            self.next_signature.number_samples / self.next_signature.sample_rate_hz < self.MAX_TIME_SECONDS
            or sum(len(peaks) for peaks in self.next_signature.frequency_band_to_sound_peaks.values()) < self.MAX_PEAKS
        ):
            self.process_input(self.input_pending_processing[self.samples_processed : self.samples_processed + 128])
            self.samples_processed += 128

        returned_signature = self.next_signature
        self.next_signature = DecodedMessage()
        self.ring_buffer_of_samples = RingBuffer(buffer_size=2048, default_value=0)
        self.fft_outputs = RingBuffer(buffer_size=256, default_value=[0.0] * 1025)
        self.spread_fft_output = RingBuffer(buffer_size=256, default_value=[0.0] * 1025)
        return returned_signature

    def process_input(self, s16le_mono_samples: List[int]):
        self.next_signature.number_samples += len(s16le_mono_samples)
        for pos in range(0, len(s16le_mono_samples), 128):
            self.do_fft(s16le_mono_samples[pos : pos + 128])
            self.do_peak_spreading_and_recognition()

    def do_fft(self, batch: List[int]):
        type_ring = self.ring_buffer_of_samples.position + len(batch)
        self.ring_buffer_of_samples[self.ring_buffer_of_samples.position : type_ring] = batch
        self.ring_buffer_of_samples.position = (self.ring_buffer_of_samples.position + len(batch)) % 2048
        self.ring_buffer_of_samples.num_written += len(batch)

        excerpt = (
            self.ring_buffer_of_samples[self.ring_buffer_of_samples.position :]
            + self.ring_buffer_of_samples[: self.ring_buffer_of_samples.position]
        )
        fft_results = np.fft.rfft(HANNING_MATRIX * excerpt)
        fft_results = (fft_results.real**2 + fft_results.imag**2) / (1 << 17)
        fft_results = np.maximum(fft_results, 0.0000000001)
        self.fft_outputs.append(fft_results)

    def do_peak_spreading_and_recognition(self):
        self.do_peak_spreading()
        if self.spread_fft_output.num_written >= 46:
            self.do_peak_recognition()

    def do_peak_spreading(self):
        origin_last_fft = self.fft_outputs[self.fft_outputs.position - 1]
        temp_1 = np.tile(origin_last_fft, 3).reshape((3, -1))
        temp_1[1] = np.roll(temp_1[1], -1)
        temp_1[2] = np.roll(temp_1[2], -2)
        origin_last_fft_np = np.hstack([temp_1.max(axis=0)[:-3], origin_last_fft[-3:]])

        i1 = (self.spread_fft_output.position - 1) % self.spread_fft_output.buffer_size
        i2 = (self.spread_fft_output.position - 3) % self.spread_fft_output.buffer_size
        i3 = (self.spread_fft_output.position - 6) % self.spread_fft_output.buffer_size

        temp_2 = np.vstack([origin_last_fft_np, self.spread_fft_output[i1], self.spread_fft_output[i2], self.spread_fft_output[i3]])
        temp_2[1] = np.max(temp_2[:2, :], axis=0)
        temp_2[2] = np.max(temp_2[:3, :], axis=0)
        temp_2[3] = np.max(temp_2[:4, :], axis=0)

        self.spread_fft_output[i1] = temp_2[1].tolist()
        self.spread_fft_output[i2] = temp_2[2].tolist()
        self.spread_fft_output[i3] = temp_2[3].tolist()
        self.spread_fft_output.append(list(origin_last_fft_np))

    def do_peak_recognition(self):
        fft_minus_46 = self.fft_outputs[(self.fft_outputs.position - 46) % self.fft_outputs.buffer_size]
        fft_minus_49 = self.spread_fft_output[(self.spread_fft_output.position - 49) % self.spread_fft_output.buffer_size]

        for bin_pos in range(10, 1015):
            if fft_minus_46[bin_pos] >= 1 / 64 and (fft_minus_46[bin_pos] >= fft_minus_49[bin_pos - 1]):
                max_neighbor = 0
                for offset in [-10, -7, -4, -3, 1, 2, 5, 8]:
                    max_neighbor = max(fft_minus_49[bin_pos + offset], max_neighbor)

                if fft_minus_46[bin_pos] > max_neighbor:
                    max_other = max_neighbor
                    for other_offset in [-53, -45, 165, 172, 179, 186, 193, 200, 214, 221, 228, 235, 242, 249]:
                        max_other = max(self.spread_fft_output[(self.spread_fft_output.position + other_offset) % self.spread_fft_output.buffer_size][bin_pos - 1], max_other)

                    if fft_minus_46[bin_pos] > max_other:
                        fft_num = self.spread_fft_output.num_written - 46
                        val = max(1 / 64, fft_minus_46[bin_pos])
                        val_prev = max(1 / 64, fft_minus_46[bin_pos - 1])
                        val_next = max(1 / 64, fft_minus_46[bin_pos + 1])

                        peak_mag = np.log(val) * 1477.3 + 6144
                        peak_mag_before = np.log(val_prev) * 1477.3 + 6144
                        peak_mag_after = np.log(val_next) * 1477.3 + 6144

                        peak_var_1 = peak_mag * 2 - peak_mag_before - peak_mag_after
                        peak_var_2 = (peak_mag_after - peak_mag_before) * 32 / peak_var_1
                        corrected_bin = bin_pos * 64 + peak_var_2

                        freq_hz = corrected_bin * (16000 / 2 / 1024 / 64)
                        if 250 < freq_hz < 520:
                            band = FrequencyBand.hz_250_520
                        elif 520 <= freq_hz < 1450:
                            band = FrequencyBand.hz_520_1450
                        elif 1450 <= freq_hz < 3500:
                            band = FrequencyBand.hz_1450_3500
                        elif 3500 <= freq_hz <= 5500:
                            band = FrequencyBand.hz_3500_5500
                        else:
                            continue

                        if band not in self.next_signature.frequency_band_to_sound_peaks:
                            self.next_signature.frequency_band_to_sound_peaks[band] = []

                        self.next_signature.frequency_band_to_sound_peaks[band].append(
                            FrequencyPeak(fft_num, int(peak_mag), int(corrected_bin), 16000)
                        )

async def recognize_song_shazam(file_path: str | Path, duration: int = 15) -> dict | None:
    """
    Recognize any song directly from audio/video file using Shazam API.
    100% Free, 0 API Keys required, fast and accurate.
    """
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", str(file_path),
        "-t", str(duration),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-"
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        raw_pcm, _ = await proc.communicate()
        if not raw_pcm or len(raw_pcm) < 3200:
            return None

        samples = np.frombuffer(raw_pcm, dtype=np.int16).tolist()
        sig_gen = SignatureGenerator()
        sig_gen.feed_input(samples)
        sig = sig_gen.get_next_signature()
        while not sig:
            sig = sig_gen.get_next_signature()
            if len(sig_gen.input_pending_processing) < 128:
                break

        if not sig:
            return None

        uri = sig.encode_to_uri()
        samplems = int(sig.number_samples / sig.sample_rate_hz * 1000)

        payload = {
            "timezone": "Asia/Tashkent",
            "signature": {"uri": uri, "samplems": samplems},
            "timestamp": int(time.time() * 1000),
            "context": {},
            "geolocation": {}
        }

        url = f"https://amp.shazam.com/discovery/v5/en-US/US/android/-/tag/{str(uuid.uuid4()).upper()}/{str(uuid.uuid4()).upper()}?sync=true"
        headers = {
            "X-Shazam-Platform": "IPHONE",
            "X-Shazam-AppVersion": "14.1.0",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    track = data.get("track")
                    if track:
                        title = track.get("title", "").strip()
                        artist = track.get("subtitle", "").strip()
                        album = ""
                        sections = track.get("sections", [])
                        for s in sections:
                            if s.get("type") == "SONG":
                                for meta in s.get("metadata", []):
                                    if meta.get("title") == "Album":
                                        album = meta.get("text", "")
                        
                        cover_art = track.get("images", {}).get("coverarthq") or track.get("images", {}).get("coverart", "")
                        return {
                            "title": title,
                            "artist": artist,
                            "album": album,
                            "cover_art": cover_art,
                            "query": f"{artist} - {title}".strip(" -")
                        }
    except Exception as e:
        logger.error(f"Error in Shazam recognition: {e}")

    return None
