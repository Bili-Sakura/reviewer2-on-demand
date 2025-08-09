# System goals (recap)

* One-shot, full-paper reviews (ICLR/OpenReview structure) by GPT-5 under three tone personas (Praise / Neutral / Harsh).
* Judges (Claude primary) score helpfulness, toxicity, and harshness (all 1–7).
* Deterministic decoding (T=0, top\_p=1); enforce 600–800 word reviews.
* Data written as JSONL (FULL-20 schema), paper\_id = `ml_` + `blake2s(lower(title))[:8]`.
* Pilot: 10 papers × 3 arms = 30 reviews; later 90.

---

# 1) Repository layout

```
repo/
  ├─ README.md
  ├─ LICENSE
  ├─ requirements.txt         
  ├─ .env.example             # API key names
  ├─ config/
  │   └─ default.yaml         # knobs: concurrency, timeouts, paths, model ids, judge settings
  ├─ data/
  │   ├─ papers/              # cached PDFs
  │   └─ cache/               # extracted text/figures, model caches
  ├─ outputs/
  │   ├─ reviews/             # raw model outputs (per arm)
  │   ├─ judges/              # judge raw outputs
  │   └─ aggregates/          # final JSONL, charts, tables
  ├─ logs/
  └─ src/
      ├─ r2core/              # library code
      │   ├─ io.py
      │   ├─ hashing.py
      │   ├─ schema.py
      │   ├─ prompts.py
      │   ├─ mineru.py
      │   ├─ vision.py
      │   ├─ models.py
      │   ├─ judges.py
      │   ├─ review.py
      │   ├─ qc.py
      │   ├─ orchestrator.py
      │   └─ charts.py
      └─ cli/
          └─ r2.py            # click/typer CLI
```

---

# 2) Configuration (YAML)

```yaml
# config/default.yaml
paths:
  pdf_dir: data/papers
  cache_dir: data/cache
  out_reviews: outputs/reviews
  out_judges: outputs/judges
  out_jsonl: outputs/aggregates
runtime:
  timezone: "Asia/Tokyo"
  seed: 0                       # informational; T=0 used
  concurrency: 3                # per provider; respect rate limits
  request_timeout_s: 120
models:
  reviewer:
    id: "gpt-5"
    temperature: 0
    top_p: 1
  judge:
    id: "claude"                # primary J2
limits:
  review_min_words: 600
  review_max_words: 800
  max_pdf_pages: 200            # soft cap; warn above
prompts:
  persona_version: "A"
  structure: "Use the ICLR/OpenReview structure: Summary; Strengths; Weaknesses; Questions; Overall [1–10]; Confidence [1–5]. Keep the review to 600–800 words."
mineru:
  enabled: true
  keep_layout: true
  include_appendix: true
vision:
  send_figures: true
  include_captions: true
judging:
  retries: 2
  parse_strict: true
  toxicity_flag_threshold: 5
```

---

# 3) Data contracts

## 3.1 Input per paper

```json
{
  "paper_title": "string",
  "paper_url": "https://...pdf | openreview | arxiv",
  "source_type": "your-library | arxiv | openreview"
}
```

## 3.2 FULL-20 JSONL (one object/line)

Exact keys and types:

* `paper_id: str` — `ml_` + `blake2s(lower(title))[:8]`
* `paper_title: str`
* `arm: "praise" | "neutral" | "harsh"`
* `model: "gpt-5"`
* `decoding: {"temperature":0,"top_p":1}`
* `persona_version: "A"`
* `content_scope: "FULL+FIG"`
* `review_text: str` (600–800 words)
* `word_count: int`
* `helpfulness_1to7: int|null`
* `toxicity_1to7: int|null`
* `harshness_1to7: int|null`
* `run_id: str`  (e.g., `pilot001_h`)
* `timestamp_iso: str` (ISO-8601, JST, e.g., `2025-08-09T13:00:00+09:00`)
* `source_type: str`
* `paper_url: str`
* `fig_mode: "VISION"`
* `judge_model: "Claude"`
* `toxicity_flag_tau5: bool`
* `notes: str`

Validation (hard):

* Presence and exact key names.
* Types match; judge scores either `int ∈ [1,7]` or null before augmentation.
* `word_count ∈ [600, 800]`.
* `toxicity_flag_tau5 == (toxicity_1to7 >= 5)` if scores present.

---

# 4) Core library modules (specs)

## 4.1 `hashing.py`

```python
def paper_id_from_title(title: str) -> str:
    """
    Lowercase title, compute BLAKE2s, hex[:8], prefix with 'ml_'.
    """
```

## 4.2 `io.py`

* `download_pdf(url: str, dest: Path) -> Path` (idempotent cache; HTTP timeouts; checksum).
* `resolve_openreview_or_arxiv(url) -> pdf_url` (simple resolver).
* `read_jsonl(path) -> Iterable[dict]`
* `append_jsonl(path, record: dict) -> None`
* `atomic_write(path, bytes) -> None`

## 4.3 `mineru.py` (extraction)

* `extract_full_text(pdf_path: Path) -> dict` → `{title, abstract, sections: [ {heading, text} ], appendix: [...]}`
* `extract_figures(pdf_path: Path) -> list[ {image_path, caption, figure_id} ]`
* Guarantees:

  * Includes main text + appendix when available.
  * Preserves figure order; captions kept.
  * If MinerU fails, fall back to `pdfminer` text-only and log `notes+="mineru_fallback"`.

## 4.4 `vision.py`

* `package_figures(figs: list) -> list[VisionPart]`
* Ensure every image has a caption string; if missing, use `"Figure {n} (no caption extracted)."`

## 4.5 `prompts.py`

```python
def build_persona_line(arm: str) -> str:
    # praise | neutral | harsh (Version A)

def build_review_prompt(arm: str, meta: dict, content: dict) -> list[dict]:
    """
    Returns a chat/vision message list ready for GPT-5:
    - system: tone persona line
    - user: title, abstract, full text (concise concatenation), plus figures (vision parts)
    - always append the structure/length instruction verbatim
    """
```

Persona A lines (verbatim):

* **Praise**: “Act as a supportive mentor reviewer. Start with strengths. Phrase critiques as suggestions. Be specific. No toxicity.”
* **Neutral**: “Act as an impartial senior reviewer. Balance strengths and weaknesses. Evidence-first. Professional tone.”
* **Harsh**: “Act as a tough, exacting reviewer. Lead with major flaws. Blunt and concise. No insults or slurs.”
* **Always add**: “Use the ICLR/OpenReview structure: Summary; Strengths; Weaknesses; Questions; Overall \[1–10]; Confidence \[1–5]. Keep the review to 600–800 words.”

## 4.6 `models.py`

Abstractions over providers with strict decoding:

```python
class ReviewerClient:
    def review(self, messages: list, images: list|None) -> str  # returns raw text

class JudgeClient:
    def score_helpfulness(self, title: str, abstract: str, review: str) -> int
    def score_toxicity(self, review: str) -> int
    def score_harshness(self, review: str) -> int
```

* Enforce `{temperature:0, top_p:1}` (greedy).
* Timeouts + retries with exponential backoff + jitter.
* Log `model_version` if available from response headers.

## 4.7 `review.py` (post-processing)

* `word_count(text) -> int` (whitespace tokens; collapse multiple spaces; strip code blocks).
* `enforce_window(text, min_w=600, max_w=800) -> str`

  * If `<600`: append “Concise elaboration” prompt once (`assistant-self-critique`) to expand; else if `>800`: trim trailing verbosity without cutting section headers.
* `validate_structure(text) -> bool`

  * Must include 6 headers: `Summary`, `Strengths`, `Weaknesses`, `Questions`, `Overall [1–10]`, `Confidence [1–5]`.
* `parse_overall_confidence(text) -> (int|None, int|None)` — **Do not** trust; these are part of the review body only; stored inside `review_text` and not surfaced as external numeric fields.

## 4.8 `judges.py`

Judge prompts (verbatim, already approved):

* **Helpfulness (HJ-ABS)**: use title+abstract + review; output must be `helpfulness: N` + one-sentence rationale.
* **Toxicity (TJ-NO)**: review only; output `toxicity: N` + rationale.
* **Manipulation Check (MCJ-NO)**: review only; output `harshness: N` + rationale.

Parsing:

* Strict regex for `helpfulness:\s*([1-7])` etc.
* If parse fails or out of range, re-ask **with the original instruction prepended by**: “Return only ‘<metric>: N’ on the first line, then one sentence rationale.” (up to 2 retries).
* Return `(score:int, rationale:str)` but only scores are persisted in FULL-20; rationals saved under `outputs/judges/` for audit.

## 4.9 `qc.py`

* **Schema check**: exact keys; types; allowed enums; `word_count` range.
* **Pilot success checks** (Option A) over an aggregate file:

  * Δ helpfulness (praise − harsh) ≥ 0.5
  * Order in harshness: praise < neutral < harsh with steps ≥ 0.5
  * Toxicity flags (τ5): 0 in praise, ≤1 total across 30
* **Run integrity**: every input paper has exactly 3 reviews (one per arm).

## 4.10 `orchestrator.py`

End-to-end stages:

1. **Ingest**: read paper list; resolve and download PDFs; compute `paper_id`.
2. **Extract**: MinerU text + figures; cache results.
3. **Prompt**: build three tone prompts (A) and save copies under `outputs/reviews/{paper_id}/prompts/`.
4. **Generate**: call GPT-5 with FULL+FIG (ONE-SHOT). Save raw text per arm.
5. **Post-process**: enforce 600–800 words, validate structure; if fail → one retry with minimal “please follow structure exactly” reminder; else flag for manual review.
6. **Write JSONL stub** (missing only `review_text`, `word_count`, scores).
7. **Augment**: judge with Claude (HJ, TJ, MCJ). Fill scores; compute `toxicity_flag_tau5`.
8. **QC**: validate schema; per-run dashboards/summary CSV; pilot success metrics.
9. **Aggregate**: concatenate to `outputs/aggregates/run_{run_id}.jsonl`.
10. **Charts**: produce small figures for blog: dose–response, harshness vs helpfulness, toxicity vs harshness.

---

# 5) CLI design (Typer/Click)

```
# ingest & cache PDFs
r2 ingest --list inputs/papers.csv --run-id pilot001

# extract text+figures
r2 extract --run-id pilot001

# generate 3 reviews per paper
r2 review --run-id pilot001 --arms praise,neutral,harsh --concurrency 3

# judge all reviews with Claude
r2 judge --run-id pilot001

# quality control + aggregate
r2 qc --run-id pilot001
r2 aggregate --run-id pilot001

# quick end-to-end (dangerous if rate-limited)
r2 all --list inputs/papers.csv --run-id pilot001
```

CSV columns for `--list`: `paper_title,paper_url,source_type`

---

# 6) Exact prompt builders

## 6.1 System/tone line (choose per arm)

* Praise: `Act as a supportive mentor reviewer. Start with strengths. Phrase critiques as suggestions. Be specific. No toxicity.`
* Neutral: `Act as an impartial senior reviewer. Balance strengths and weaknesses. Evidence-first. Professional tone.`
* Harsh: `Act as a tough, exacting reviewer. Lead with major flaws. Blunt and concise. No insults or slurs.`

## 6.2 Structure line (always appended)

`Use the ICLR/OpenReview structure: Summary; Strengths; Weaknesses; Questions; Overall [1–10]; Confidence [1–5]. Keep the review to 600–800 words.`

## 6.3 User content (sketch)

* Title
* Abstract
* “Main text (abridged for token fit)” + appendix key bits
* Figures (as vision parts), each with caption text
* Short reminder: “Critique the *paper’s content*; avoid personal remarks; keep non-toxic.”

---

# 7) Determinism & length enforcement

* **Decoding**: `{temperature:0, top_p:1, n:1}`.
* **Length**:

  * Pre-flight: include the 600–800 instruction in system/user.
  * Post-flight: measure `word_count`; if `<600` or `>800`:

    * One corrective turn: “Please adjust to 600–800 words without changing content or scores.”
    * Re-count; if still out of range, **truncate or expand minimally** (append short clarifications to Strengths/Weaknesses) and tag `notes+="length_adjustment"`.

---

# 8) Timestamps, IDs, and naming

* `timestamp_iso`: compute with `Asia/Tokyo` timezone at write time.
* `run_id`: `pilot{seq}_{arm_initial}` for per-arm files is OK, but in JSONL keep the run ID common (e.g., `pilot001`) and the `arm` field disambiguates.
* File naming:

  * Reviews: `outputs/reviews/{paper_id}/{arm}.txt`
  * Prompts: `outputs/reviews/{paper_id}/prompts/{arm}.json`
  * Judges: `outputs/judges/{paper_id}/{arm}_{metric}.txt`
  * Final line mirrors `paper_title` precisely as provided.

---

# 9) Error handling & retries

* **Network**: exponential backoff (base 2), jitter ±20%, max 3 attempts.
* **Provider errors**: on 429/5xx, respect `Retry-After` if present; otherwise backoff.
* **Extraction failures**: fall back to text-only; set `notes+="mineru_fallback"`.
* **Judge parsing**: up to 2 re-asks with stricter formatting instruction.
* **Poison content** (rare): if toxicity judge ≥ 6, quarantine file to `outputs/reviews/quarantine/` and require human sign-off.

---

# 10) Quality control checklist (per line)

* Keys present and exact (FULL-20).
* Types correct.
* `model=="gpt-5"`, `persona_version=="A"`, `content_scope=="FULL+FIG"`, `fig_mode=="VISION"`, `judge_model=="Claude"`.
* Word count 600–800.
* Scores either all null (pre-augmentation) or all ints in \[1,7] (post).
* `toxicity_flag_tau5` consistent with toxicity score.
* Optional lint: section headers present in `review_text`.

---

# 11) Pilot success computation

Implement a small aggregator producing:

* Per-arm means for helpfulness, toxicity, harshness.
* Δ helpfulness (praise − harsh).
* Check ordering in harshness: `praise < neutral < harsh` with ≥0.5 step.
* Count τ5 flags per arm; assert 0 in praise; ≤1 overall out of 30.

---

# 12) Security, privacy, compliance

* **Secrets**: use env vars (`GPT5_API_KEY`, `CLAUDE_API_KEY`, `MINERU_API_KEY`).
* **Logging**: redact API keys, document IDs; keep prompts and outputs in repo only if papers are public; otherwise store outside VCS.
* **Anonymity**: for OpenReview double-blind, scrub author names if extracted; keep `source_type` and URLs but avoid copying author lists into outputs.
* **Toxicity**: prompts explicitly discourage; judges enforce; human review before publishing examples.

---

# 13) Testing strategy

### Unit tests

* `paper_id_from_title("Gaussian Widgets") == "ml_3f9a2c7b"` (use a frozen vector).
* Word counter on representative texts.
* JSONL validator catches missing/extra keys and type mismatches.
* Prompt builder includes persona + structure verbatim.

### Integration tests

* End-to-end on a tiny PDF fixture (2–3 pages, 1 figure), with mocked model/judge clients returning canned outputs.
* Regression “golden” tests on prompt text snapshots.

### Contract tests

* Judge parsing from various plausible Claude outputs; ensure robustness.

---

# 14) Minimal JSONL stub writer

Before generation (per arm), write a stub with:

* All metadata filled,
* `review_text=""`, `word_count=0`,
* judge scores `null`,
* `toxicity_flag_tau5=false`,
  so downstream stages can be resumed idempotently.

---

# 15) Charts for the blog (automated)

* **Dose–response**: bar/line of mean harshness by arm.
* **Harshness ↔ Helpfulness**: scatter with per-review points, trendline (OLS).
* **Toxicity vs Harshness**: violin/box by arm + τ5 count badges.
* Export PNG + lightweight CSVs to `outputs/aggregates/figures/`.

---

# 16) Example pseudocode: one paper, three arms

```python
def run_one_paper(paper, run_id, cfg):
    pid = paper_id_from_title(paper["paper_title"])
    pdf = ensure_pdf(paper["paper_url"], pid)
    content = extract(pdf)  # text + figures
    results = []
    for arm in ["praise", "neutral", "harsh"]:
        prompt = build_review_prompt(arm, meta=paper, content=content)
        raw = reviewer.review(prompt.messages, images=prompt.images)
        text = normalize_whitespace(raw)
        text = enforce_window(text, cfg.limits.review_min_words, cfg.limits.review_max_words)
        assert validate_structure(text), "bad_structure"
        wc = word_count(text)
        line = make_full20_stub(paper, pid, arm, run_id)
        line.update({
            "review_text": text,
            "word_count": wc,
            "timestamp_iso": now_jst_iso()
        })
        # Judges
        h = judge.score_helpfulness(paper["paper_title"], content["abstract"], text)
        t = judge.score_toxicity(text)
        m = judge.score_harshness(text)
        line.update({
            "helpfulness_1to7": h,
            "toxicity_1to7": t,
            "harshness_1to7": m,
            "toxicity_flag_tau5": bool(t >= 5)
        })
        validate_full20(line)
        append_jsonl(out_path(run_id), line)
        results.append(line)
    return results
```

---

# 17) Operator quick start (scripted)

1. Prepare `inputs/papers.csv` with 10 rows: `paper_title,paper_url,source_type`.
2. `r2 all --list inputs/papers.csv --run-id pilot001`
3. Inspect `outputs/aggregates/run_pilot001.jsonl`.
4. `r2 qc --run-id pilot001` to see pilot success diagnostics + charts.

---

# 18) Nice-to-haves / backlog

* Committee judge (GPT-5 + Claude) with median (J3).
* Same-model judge (J1) for ablation.
* Lightweight toxicity pre-filter (keyword list) to reduce judge calls on obviously clean reviews.
* HTML report bundling prompts, reviews, and judge rationales per paper.
* Parallel runner with provider-aware rate limiting.
* Optional “re-review” mode that feeds author rebuttals (future).

---

