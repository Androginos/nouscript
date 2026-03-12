# Load analysis: 50 concurrent requests

Rough impact of **50 requests at the same time** (e.g. 50 users each sending one video at once).

---

## Per-request pipeline (what one job does)

| Stage | Resource | Notes |
|-------|----------|--------|
| **1. Download** | Network, CPU (ffmpeg), RAM | yt-dlp + ffmpeg. ~10–50 MB RAM per 10‑min video. |
| **2. Transcribe** | Groq API **or** local CPU | Chunks of 5 min (300 s). 10‑min video = 2 chunks = 2 Groq calls, or 2 local Whisper runs. |
| **3. Summary or translate** | Nous API (Hermes-4-70B) | Summary: 1 long completion. Subtitle: N batches of 20 segments = N API calls. |

---

## 50 concurrent: where the load shows up

### 1. CPU
- **If Groq is used for transcription:** CPU is mainly download + decode (ffmpeg) and some app overhead. 50 in parallel = high CPU only during download/decode.
- **If local Whisper fallback:** Each job runs Whisper in a thread (`asyncio.to_thread`). 50 concurrent = 50 Whisper runs. Whisper “small” is already heavy; 50× would saturate CPU and likely make the machine unusable (and very slow).

### 2. Memory (RAM)
- Whisper model: loaded **once** (~500 MB–1 GB for `small`).
- Per job: audio buffer (e.g. 20–80 MB for a 10–30 min video), plus transcript text and segments.
- **50 jobs:** 50 × ~50 MB ≈ **2.5 GB** only for audio; with segments and Python overhead, **4–8 GB** extra is plausible. Total process can reach **~10 GB** if all 50 are in the “heavy” phase.

### 3. Groq API (transcription)
- Groq has **rate limits** (e.g. requests per minute).
- 50 concurrent → 50 transcription requests (first chunk each) at the same time → high chance of **429 / rate limit**. More chunks (longer videos) = more calls in a short window.
- Effect: many jobs will hit “Groq failed, falling back to local” → then **local Whisper** → CPU explodes (see above).

### 4. Nous API (summary / translate)
- Hermes-4-70B (inference-api.nousresearch.com) has its own **per-minute / concurrent** limits.
- 50 summary or 50×N translate calls at once → very likely **429 or “overloaded”**-style errors.
- Effect: user-visible failures or long waits.

### 5. Network
- **Inbound:** 50 × video downloads (yt-dlp) → can be hundreds of MB to a few GB total.
- **Outbound:** 50 × (Groq + Nous) API traffic. Usually smaller than downloads but non‑negligible.

### 6. Disk / temp
- Temp files for Groq WAV chunks, yt-dlp cache, etc. 50 jobs = more temp usage; usually acceptable if disk has a few GB free.

---

## Summary table (50 concurrent)

| Resource | Rough impact |
|----------|------------------|
| **CPU** | Very high (especially if Groq is rate-limited and many fall back to local Whisper). |
| **RAM** | ~5–10 GB extra (audio buffers + segments + model). |
| **Groq** | Rate limit very likely → 429, fallback to local → more CPU. |
| **Nous** | Rate limit / overload very likely → failed summaries or translations. |
| **Network** | High during download phase; API traffic moderate. |

---

## Recommendation

- **50 concurrent** with current design (1 process, Groq + Nous + optional local Whisper) will:
  - Hit **external API limits** (Groq, Nous) first.
  - Then **CPU and RAM** on the server if many jobs fall back to local Whisper or if APIs throttle.

To support “up to 50 at the same time” you’d need:
- **Higher** or **dedicated** Groq/Nous quotas (or multiple keys with per-key limits).
- **Worker cap** well below 50 (e.g. 10–15) so the server and APIs don’t overload; the rest wait in queue.
- **Queue + clear “Server busy”** when full (already in place); optionally show approximate wait time.

Keeping **CONCURRENT_WORKERS = 10** and **queue maxsize = 20** is a reasonable balance: up to 10 real concurrent, 20 more waiting, and you avoid the worst of API limits and server load that 50 concurrent would cause.
