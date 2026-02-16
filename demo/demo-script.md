# Terra Incognita — Demo Script (3 minutes)

> **Tagline**: "Existing tools search for papers that exist. Terra Incognita discovers research that doesn't exist yet."

---

## Act 1: The Map (0:00 - 0:40)

### Setup
- Open Kibana Agent Builder with Terra Incognita Scout selected
- Dashboard tab ready in background

### Query Input
```
알츠하이머 치료에서 아직 탐험되지 않은 연구 방향을 찾아줘
```
(English: "Find unexplored research directions in Alzheimer's treatment")

### Expected Output (SURVEY)
The agent scans 6,000+ papers across 6 domains and produces a domain relevance profile:

```
Research Landscape:
  neuroscience      ████████████████████  0.91  (2,847 papers)
  pharmacology      ███████████████░░░░░  0.74  (1,203 papers)
  molecular_biology ██████████████░░░░░░  0.68  (892 papers)
  materials_science ███░░░░░░░░░░░░░░░░░  0.15  (8 papers)   <-- Gap detected
  ecology           █░░░░░░░░░░░░░░░░░░░  0.04  (1 paper)
  quantum_computing ░░░░░░░░░░░░░░░░░░░░  0.01  (0 papers)
```

### Killing Point
- "Look at materials_science — relevance 0.15, only 8 papers. That's not zero (it would be meaningless), but it's suspiciously sparse given how active both fields are individually."

---

## Act 2: The Gap (0:40 - 1:30)

### Gap Discovery (DETECT)
The agent identifies the "meaningful gap" — not a completely empty area (that would be irrelevant), but a spot where **some connection exists but almost nobody has explored it**.

### Expected Output
```
Meaningful Gap Found:

[Parameter Auto-Tuning: High density detected -> threshold adjusted to 0.10-0.20]

materials_science (relevance 0.15, 8 papers)
  Contact point analysis:
  -> "Amyloid-beta aggregation on engineered surface topographies" (2024)
  -> "Gold nanorod-mediated photothermal disruption of tau fibrils" (2025)

  Gap Definition: Materials science's "surface engineering / nanostructures"
  has a contact point with Alzheimer's "protein aggregation control",
  but cross-research is limited to only 8 papers — mostly in-vitro stage.

  Innovation Vacuum Index: 0.91 (top 2%)
```

### Killing Point
- **"Top 2%"** — The percentile ranking makes the abstract concept concrete and impressive
- **Parameter auto-tuning** — The agent adjusted its own thresholds based on the data distribution, demonstrating autonomy

---

## Act 3: The Bridge (1:30 - 2:20)

### Self-Correction Sequence (BRIDGE)
This is the demo's centerpiece. The agent searches for cross-disciplinary bridges and **visibly rejects false positives** before finding the real connection.

### Expected Output
```
Cross-Domain Bridge Search...

  [Thought Log]
  |-- Candidate 1: "Carbon nanotube neural interfaces" -- evaluating...
  |   -> REJECTED: Keyword match (nano+neural) but no mechanistic
  |      relevance to protein aggregation. Discarded.
  |-- Candidate 2: "Zwitterionic polymer brushes resist amyloid fibril formation"
  |   -> ACCEPTED: Anti-fouling mechanism = amyloid-beta aggregation
  |      inhibition via identical principle!
  |-- Re-searching with expanded anti-fouling keywords...

Unexpected Bridge Found:

Materials science deep search reveals:
"Anti-fouling polymer coatings that prevent protein adhesion"
shares the same mechanism as amyloid-beta aggregation inhibition.

Serendipity Probability: 0.84 (top 5%)
```

### Novelty Verification (VALIDATE)
```
Novelty Verification:

"Zwitterionic polymer + Alzheimer amyloid-beta + in-vivo"
  -> Cross-papers: 0  *** Completely unexplored ***
  -> Existing bridges (cross-list): 0
  -> Materials science (anti-fouling): 342 papers (very active)
  -> Neuroscience (amyloid-beta): 2,847 papers (very active)
  -> Verdict: NOVEL — Both fields are mature, but the intersection is empty
```

### Killing Point
- **Self-Correction is visible** — The audience watches the agent think, reject, and retry. This is not a chatbot — it's an autonomous scout.
- **"0 cross-papers"** — The wow moment. Two active fields, zero intersection. That's where discovery lives.
- **Mechanism match** — The bridge isn't a superficial keyword overlap. Anti-fouling coatings and amyloid aggregation inhibition share the same underlying mechanism (preventing protein adhesion).

---

## Act 4: The Watch (2:20 - 3:00)

### Discovery Card Generation (PROPOSE)
```
Discovery Card:
+----------------------------------------------+
|  Zwitterionic Polymer x                      |
|  Alzheimer's Amyloid-Beta                    |
|                                              |
|  Innovation Vacuum: top 2%                   |
|  Serendipity: top 5%                         |
|  Cross-papers: 0 -- completely unexplored    |
|                                              |
|  Confidence: HIGH                            |
+----------------------------------------------+
```

### Cloud Scheduler Demo (Automation)
Show the Cloud Scheduler setup — this is not just a demo, it's a real daily workflow:

```
"This runs automatically every day:"

Cloud Scheduler (09:00 KST)
  → ti_daily_discovery: Full 5-step exploration + auto-save
  → New Discovery Cards generated daily

Cloud Scheduler (10:00 KST)
  → ti_gap_watch: Monitor all open gaps for new papers
  → Alerts when research gaps start being filled
```

Optional: Trigger manually to show it live:
```bash
gcloud scheduler jobs run ti-daily-discovery --location=asia-northeast3
```

### Dashboard Transition
Switch to the Kibana dashboard showing:
- Gap Heatmap across all domain pairs
- Innovation Vacuum Index leaderboard
- Recent Discovery Cards
- Exploration timeline

### Closing Line
> "Terra Incognita doesn't just find papers. It finds the **spaces between papers** — where the next breakthrough is waiting."
>
> "And it does this automatically, every single day."
>
> "Powered by Elasticsearch."

---

## Preparation Checklist

### Tabs to Prepare
1. **Kibana Agent Builder** — Terra Incognita Scout selected, new conversation
2. **Kibana Dashboard** — Terra Incognita dashboard loaded with seed data
3. **Notepad** — Query text ready to paste

### Query Text (Copy-Paste Ready)
```
알츠하이머 치료에서 아직 탐험되지 않은 연구 방향을 찾아줘
```

### Pre-Demo Verification
- [ ] Agent responds to test query
- [ ] Dashboard shows seed data visualizations
- [ ] All 5 indices have data (`GET _cat/indices/ti-*?v`)
- [ ] ELSER model is deployed and running

### Timing Notes
- SURVEY step: ~5-10 seconds
- DETECT step: ~5-10 seconds
- BRIDGE + Self-Correction: ~10-15 seconds (the dramatic pause)
- VALIDATE + PROPOSE: ~5-10 seconds
- Total agent response: ~25-45 seconds
- Use the waiting time to narrate what the agent is doing

### Backup Plan
If the agent takes too long or encounters an error:
- Switch to pre-recorded output screenshots
- Use Converse API for faster response (`curl` command ready)
- Dashboard is independent of agent — always works
