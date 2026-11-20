---
# Not verified: read as search-result text only (see the note under the header)
id: short-form-functional-music
title: Short functional music (ringtones, alerts, alarms, jingles) and phone-speaker translation
domain: genre
status: partly-sourced
sources: [https://www.masteringbox.com/small-speakers/, https://blog.landr.com/make-bass-audible-phone-speakers, https://www.sonarworks.com/blog/learn/make-your-mix-sound-great-on-small-speakers, https://audiokinetic.com/en/blog/loudness-and-frequency-response-on-popular-smart-phones, https://www.cs.stir.ac.uk/~kjt/research/match/resources/documents/chi11-mcgee1.pdf, https://www.futurice.com/blog/designing-notification-sounds, https://rmit.edu.au/news/all-news/2021/apr/snooze-blues, https://pmc.ncbi.nlm.nih.gov/articles/PMC6986749, https://fhsltest.eng.buffalo.edu/publications/1064804618763268.pdf, https://ti.com/document-viewer/lit/html/sszt261]
used_by: [AGENTS.md, references/scoring/short-form-and-ringtones.md, references/workflow/director-craft.md, scripts/helpers/short_form_report.py]
updated: 2026-11-20
---

> **Not verified.** The pages above were not opened in the session that wrote this file; each line is what a search
> result said about its page, and several pages are blogs or vendor posts. A number is `per search result` (a source
> states it) or `starting value` (a working figure, not calibrated). Cite a primary source before presenting any of them
> as established.

# Short functional music

## 1. What a phone speaker returns

| Finding | Basis |
|---|---|
| Phones and tablets claim a wide range, but the response that is actually heard starts around 200-400 Hz | per search result (MasteringBOX) |
| Most mobile hardware filters out everything below about 200 Hz and almost all of it is gone by 100 Hz | per search result (LANDR) |
| One measured phone dropped quickly below 600 Hz and above 9 kHz, leaving roughly 500 Hz to 10 kHz usable | per search result (Sonarworks, one device) |
| Sources disagree on the cutoff and it varies with the device, so 300 Hz is a test point, not a specification | per search result |
| Bass reaches a small speaker through its upper harmonics, so a bass part is carried by the 250-700 Hz region and by saturation, not by a boost below 80 Hz | per search result (Sonarworks, LANDR) |
| A small speaker is often a single driver: sum the mix to mono and check it | per search result (MasteringBOX) |

## 2. Hook and length

| Finding | Basis |
|---|---|
| Short musical snippets used as alerts are learnable and keep the privacy of an earcon (a CHI 2011 study of "Musicons"); the excerpt gives no length figures | per search result (McGee-Lennon et al.) |
| The recognisable part of an alert sits in the first 1-3 seconds; recognition improves when the first 2-5 seconds of a hook are present | per search result (informal blog claims, not controlled studies) |
| Calls and alerts are made 3-15 seconds long and loopable; a text-message sound is shorter | per search result (a production guide, a commentary piece) |
| Tempo, frequency, timbre and repetition set how urgent an alert reads; a clear transient is what draws attention | per search result (Futurice) |

## 3. Working figures for a ringtone

None of these comes from a source. They are the values the references start from; change them to the brief and say so.

| Quantity | Starting value | Why it is a starting value |
|---|---|---|
| The hook begins | within 3 s of the start, on the first or second beat | follows section 2; a listener has not yet decided to answer |
| The hook motif | 3-6 notes, one leap and steps | short enough to hum after one hearing; no study run |
| Loudness | -14 LUFS integrated, -1.5 dBTP | a ringtone competes with room noise, and a phone usually converts it to a lossy format, so the ceiling is the engine default; not calibrated |
| Share of energy in 300-5000 Hz | at least 0.85 | follows section 1; the share is a proxy for what the speaker returns |
| Share of energy below 200 Hz | at most 0.05 | follows section 1 |
| Loop seam | the end-to-start sample step is no larger than the 99.9th percentile of the steps inside the piece; the level across the seam within 3 dB | derived from the piece itself; the 3 dB is a working figure |
| Note density | varies by at least 0.15 (spread of notes per bar across 4-bar windows) | a flat arrangement is one texture; the figure is a working one |

## 4. What a measurement can and cannot say

`scripts/helpers/short_form_report.py` measures the seam, the band, the first seconds, the return of the opening shape
and the density. It cannot say a tune is catchy, a blend is pleasant, or an instrument is believable: those are a
listener's judgement, and the report states that it did not make them.

## 5. Alarms: waking someone, and urgency

| Finding | Basis |
|---|---|
| A survey of 50 people (RMIT, PLoS ONE 2020) tied melodic alarm tones, "a tune that is easy to sing or hum along to", to less perceived grogginess on waking, and neutral tones to more; no link was found with objective sleep inertia | per search result (the study is correlational, self-reported and small) |
| A follow-up compared a designed melodic alarm with a classic beeping one: faster and more accurate responses after waking with the melodic one; the authors say the best mix of melody and rhythm is not yet known | per search result (RMIT news, The Conversation) |
| A claim that dominant frequencies around 500 Hz wake best appears in popular press; no primary study was found | per search result (not used as a rule) |
| IEC 60601-1-8 (medical alarms), tonal edition: pulse fundamental 150-1000 Hz, at least four harmonics within 15 dB of the fundamental, harmonics in 300-4000 Hz; a high-priority burst is three pulses then two, each pulse 100-300 ms | per search result (Buffalo study, TI article; the edition's tables were not opened) |
| The same standard codes urgency with speed, rhythm, repetition, duration, pitch and amplitude envelope; its 2020 amendment replaced the tonal melodies with auditory icons and says loudness should not carry urgency | per search result (VDE preview listing; not opened) |

An alarm is not a medical device and none of the figures above is a requirement for one. They name the levers.

### Working figures for a wake-up alarm

None of these comes from a source. Change them to the brief and say so.

| Quantity | Starting value | Why it is a starting value |
|---|---|---|
| Form | one cell that a phone loops, in four stages of rising pressure | follows the urgency levers above; no listening test run |
| Pressure per stage | more notes per second, a higher register, a new layer, a louder section | the levers the standard names, taken as a direction only |
| Loudness | -12 LUFS integrated, -1.5 dBTP | an alarm must carry in a room and wake a sleeper; the ceiling is the engine's; not calibrated |
| The first stage | a hum-able tune on the clearest plucked attack, quiet enough not to startle | the melodic-alarm finding above |
| The last bars | settle on the tonic chord the loop restarts on | the gate asks for a release; a phone repeats the file |
