# Reviewer #2, On Demand: Prompt-Guided Harshness vs. Praise in GPT-5

Calibrate the tone of model feedback—from tough “Reviewer #2” to warm encouragement—using prompt design, with reproducible evals and open contributions.

> Project status: **alpha scaffolding**. Core modules and CLI are stubbed; wire model/extraction to go end-to-end.

## Quick start

1. Create a CSV like `inputs/papers.csv` with columns: `paper_title,paper_url,source_type`.
2. Create a virtualenv and install:

```sh
pip install -e .
```

3. Generate stubs (per paper × arms) into `outputs/aggregates/run_<id>.jsonl`:

```sh
r2 review --list inputs/papers.csv --run-id pilot001
```

4. Basic QC on a JSONL:

```sh
r2 qc --in-jsonl outputs/aggregates/run_pilot001.jsonl
```

5. Validate against JSON Schema + extra rules:

```sh
python scripts/validate_jsonl.py --jsonl outputs/aggregates/run_pilot001.jsonl --schema schema/full-20.json
```

## Contributing

We welcome issues and PRs.

## Citation

If this repo helps your work, consider citing:

```bibtex
@software{reviewer2_on_demand_2025,
  title        = {Reviewer \#2, On Demand: Prompt-Guided Harshness vs. Praise in GPT-5},
  author       = {Sakura},
  year         = {2025},
  url          = {https://github.com/Bili-Sakura/reviewer2-on-demand}
}
```
