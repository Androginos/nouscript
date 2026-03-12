# Hackathon Plan: Hermes-Heavy Pipeline & Summary Quality

**Goal:** Win the hackathon with a clear **Hermes Agent–centric** story and **stronger summary/analysis output**.

**Decisions:** Keep **all analysis and translation on Hermes (model)** — no offload to light services. We want the best quality and a single, coherent “Hermes does it” pipeline.

---

## 1. Hermes-heavy pipeline narrative (for the pitch)

**One-line:** “From link to insight: Hermes Agent drives the entire pipeline — download, transcribe, analyze, translate.”

**Flow to present:**

1. **User** → sends video link (Telegram / web / Hermes chat).
2. **Hermes Agent / skill** → orchestrates: calls NouScript API for **download + transcribe** (or full pipeline). The API is the “engine” that runs **Hermes-4-70B** for analysis and translation.
3. **Model (Hermes-4-70B)** → does **analysis** (summary, structure, genre-aware) and **translation** (subtitles, fluent). All reasoning and language quality come from Hermes.
4. **Output** → summary (.txt), subtitles (.srt), in 14 languages.

**Message:** “We don’t split the brain: one model, one agent stack — Hermes for reasoning and language, end to end.”

**Assets to stress:**
- Hermes Agent (gateway, skills, Telegram).
- Hermes-4-70B for both **summary** and **translation** (no cheap substitute).
- Skill explicitly triggers download → transcribe → summarize (and for subtitles, translate).
- Multi-channel: web, Telegram Sumbot, Hermes chat — same Hermes-backed API.

---

## 2. Summary logic & output quality (improvements)

**Current:** One-shot prompt: genre detection, then structured summary (Video Type, Main Topic, Key Points, Conclusion).

**Directions to improve:**

### A) Stronger system prompt (reasoning + structure)

- **Longer <think> block:** Encourage step-by-step: identify genre → main narrative → turning points → takeaways.
- **Stricter output format:** Optional subsections (e.g. “Key quote”, “Action items”, “Controversy/ambiguity”) for certain genres.
- **Language:** Explicit “Write in a clear, engaging way; avoid filler; one idea per bullet.”

### B) Two-step summary (optional, for long content)

- **Step 1:** Model produces a short “abstract” (2–3 sentences) + bullet outline.
- **Step 2:** Same model expands into full summary using the outline. Keeps structure and avoids drift.

### C) Genre-specific templates

- **Tech review:** Specs, pros/cons, verdict, “Best for whom”.
- **Tutorial/educational:** Learning outcomes, prerequisites, steps summary.
- **Podcast/interview:** Guests, main theses, standout quotes.
- **Gaming:** Game, genre, highlights, vibe (casual/competitive).

Prompt selects template from detected genre and fills it.

### D) Output polish

- **Length control:** “Summary should be between 150–400 words for short videos, 300–600 for long.”
- **Headings:** Always `## Video Type`, `## Main Topic`, `## Key Points`, `## Conclusion` (and optional extras).
- **No boilerplate:** “Do not start with ‘This video is about…’; start with the main point.”

### E) Metadata usage

- Use title, channel, description, tags more explicitly: “Use the title and description to anchor the main topic; use the transcript for evidence and nuance.”

**Concrete next step:** Implement (A) + (D) + (E) first (prompt upgrade + structure + metadata). Then add (C) for genre templates; (B) only if you want extra polish for long videos.

---

## 3. Translation (keep on Hermes, optional tweaks)

- **Keep:** All subtitle translation via Hermes-4-70B (batch + single fallback). No move to a light service.
- **Optional:** Add one line to the translator system prompt: “Keep the tone and register of the original (formal/casual/slang) where appropriate in the target language.” Improves perceived fluency without changing architecture.

---

## 4. Hackathon checklist

| Item | Status / action |
|------|------------------|
| **Pitch:** “Hermes-heavy pipeline” — one model, one stack | Narrative doc (this file) |
| **Demo:** Show Telegram (Sumbot + Hermes chat) + web, same API | Ready |
| **Summary quality:** Stronger prompt, structure, genre awareness | Implement A, D, E then C |
| **Translation:** Stay on Hermes, optional fluency tweak | Optional prompt tweak |
| **Slide / README:** Emphasize Hermes Agent + Hermes-4-70B, no “we use a cheap translator” | Update README / pitch deck |
| **Code / repo:** Clear separation: skill vs API vs model; comments that highlight “Hermes does analysis and translation” | Light pass on docs/comments |

---

## 5. Translation-offload plan (closed)

The previous idea of moving translation to a light service (**PLAN_TRANSLATION_OFFLOAD.md**) is **not** pursued. We keep analysis and translation on Hermes for quality and for a single, hackathon-friendly story: **Hermes does the analysis and the translation.**

---

**Next step:** Pick 2–3 summary improvements (e.g. A + D + E), then we can draft the exact prompt changes in `app.py` (e.g. in `summarize_with_nous`).
