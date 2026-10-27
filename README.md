# TCM-DiagCommit

**A TCM-SD-Derived Benchmark for Evidence-Conditioned Syndrome Selection and Commitment**

Erwei Hou and Yue Hu  
Beijing University of Posts and Telecommunications, Beijing, China  
{houerwei, huyue2023}@bupt.edu.cn

## Overview

TCM-DiagCommit evaluates how a model performs evidence-conditioned diagnostic
decisions in Traditional Chinese Medicine (TCM) syndrome differentiation, rather
than one-shot final-label selection over a complete clinical record. Standard
TCM syndrome-differentiation evaluation hides three behaviors: whether a model
can tell semantically neighboring syndrome labels apart from easy random
distractors, whether its prediction is revised as evidence fields are revealed,
and whether it should commit or withhold a diagnosis under uncertainty. This
benchmark makes those behaviors measurable and comparable.

The benchmark is derived from the public TCM-SD / ZY-BERT resource while keeping
its 148 source syndrome labels as gold. It converts 1,834 source clinical cases
into paired task rows and defines a fixed action contract (commit, acquire,
defer, abstain) scored by a benchmark-defined policy.

## Benchmark at a glance

| Property | Value |
| --- | --- |
| Source clinical cases | 1,834 |
| Syndrome labels (ontology) | 148 |
| Dev cases | 919 |
| Test cases | 915 |
| Task files | 26 (13 dev + 13 test) |
| Task rows | 23,842 (11,947 dev + 11,895 test) |
| Base source records | 1,834 (one per case) |

## Task families

Every source case is rendered as paired task rows. The release contains 13 task
variants per split, grouped into four capability families. Across all variants
the gold label is always present in the candidate set, so failure reflects a
diagnosis or ranking error rather than an open-vocabulary mismatch.

| Family | Variants | Evaluated behavior |
| --- | --- | --- |
| Hard syndrome differentiation | `random10`, `hard10`, `hard20`, `full148` | Semantic candidate discrimination. `random10` is an easy closed-set control; `hard10`/`hard20` use profile-neighbor distractors; `full148` uses the full 148-label vocabulary. |
| Diagnostic commitment control | `insufficient_t1_hard10`, `insufficient_t1_hard20`, `insufficient_t2_hard10`, `insufficient_t2_hard20` | Commitment behavior under staged, incomplete evidence (t1 = chief complaint only; t2 = + description/history). |
| Counterfactual evidence sensitivity | `tongue_pulse_swap_hard10` | Fixed gold tongue/pulse perturbation to test reliance on inspection evidence. |
| Shortcut and evidence-ablation control | `candidate_only_hard10`, `chief_only_hard10`, `no_tongue_pulse_hard10`, `tongue_pulse_only_hard10` | Sanity checks that remove or isolate individual evidence fields. |

In addition, `source/dev_cap10_919.jsonl` and `source/test_cap10_915.jsonl`
contain the base clinical record for every case (one row per case).

## Staged evidence

Each task exposes one of three evidence views, following the information flow of
a TCM consultation:

- **t1** — chief complaint only.
- **t2** — chief complaint + description / history.
- **t3** — t2 + detection (inspection, tongue/pulse-style observations).

Tasks with `evidence_mode = full` present the t3 view. The
`insufficient_t1_*` and `insufficient_t2_*` variants are the dedicated
partial-evidence commitment stress tests.

## Repository structure

```
TCM-DiagCommit/
├── README.md
├── LICENSE                      # MIT (code)
├── LICENSE-DATA.md              # CC BY 4.0 (dataset)
├── configs/
│   └── benchmark_config.json    # release metadata and variant map
├── data/
│   ├── dev/                     # 13 task variants + source, 919 cases
│   ├── test/                    # 13 task variants + source, 915 cases
│   └── metadata/
│       ├── prediction_schema.json
│       ├── task_manifest.json
│       └── syndrome_vocabulary.json
├── src/
│   └── tcm_diagcommit/           # scoring library (metrics, commitment, schemas)
└── scripts/
    └── run_eval.py               # evaluation entry point
```

## Data format

Each task row is a JSON object:

| Field | Description |
| --- | --- |
| `case_id` | Dataset-local task row id. |
| `source_case_id` | Dataset-local source case id (stable across variants). |
| `source_split` | `dev` or `test`. |
| `subject_id` | Remapped, non-identifying subject id. |
| `lcd_id`, `lcd_name` | Disease code and name (中医病证分类). |
| `task_family` | One of the four capability families. |
| `variant` | Task variant name (e.g. `hard20`). |
| `evidence_mode` | `full`, `t1`, or `t2`. |
| `chief_complaint`, `description`, `detection` | Clinical text fields (evidence). |
| `label` | Gold syndrome label (always in `candidate_syndromes`). |
| `candidate_syndromes` | Candidate list; the gold label is always included. |
| `metadata` | Per-row provenance (candidate policy, label position, etc.). |

A model prediction is submitted by copying a task row and filling a
`prediction` object (see `data/metadata/prediction_schema.json`):

```json
{
  "top1": "syndrome copied exactly from candidate_syndromes",
  "top3": [["syndrome", 0.0], ["syndrome", 0.0], ["syndrome", 0.0]],
  "confidence": 0.0,
  "reason": "brief evidence-grounded rationale",
  "action": "commit | acquire | defer | abstain",
  "need_more_evidence": false
}
```

## Scoring

The evaluation code is pure Python standard library (Python 3.8+). To score a
set of prediction files:

```bash
python scripts/run_eval.py --task static \
    --predictions path/to/predictions.jsonl \
    --out-dir results/my_run

python scripts/run_eval.py --task progressive \
    --predictions path/to/predictions.jsonl \
    --out-dir results/my_run

python scripts/run_eval.py --task commitment \
    --predictions path/to/predictions.jsonl \
    --out-dir results/my_run
```

`--task static` reports top-1 / top-3 accuracy and candidate-set metrics.
`--task progressive` reports stage-wise and transition metrics across t1/t2/t3.
`--task commitment` reports the action-contract cost under the benchmark policy;
cost weights are configurable (`--wrong-commit-cost`, `--evidence-cost`,
`--defer-cost`, `--abstain-cost`).

## Privacy and provenance

The benchmark is derived from the public TCM-SD / ZY-BERT clinical resource.
Before release, raw identifiers (`user_id`) were removed, case and source ids
were remapped to dataset-local identifiers, and high-risk direct PII patterns
(including dates) were masked. Each row is traceable to one source case but
contains no re-identifying information.

## License

- **Code** (everything under `src/` and `scripts/`): MIT License. See
  [LICENSE](LICENSE).
- **Dataset** (everything under `data/`): Creative Commons Attribution 4.0
  International (CC BY 4.0). See [LICENSE-DATA.md](LICENSE-DATA.md). When you
  use the dataset, attribute the TCM-DiagCommit authors and the original
  TCM-SD / ZY-BERT source.

## Citation

```bibtex
@inproceedings{hou2026tcmdiagcommit,
  title     = {TCM-DiagCommit: A TCM-SD-Derived Benchmark for Evidence-Conditioned
               Syndrome Selection and Commitment},
  author    = {Hou, Erwei and Hu, Yue},
  booktitle = {Proceedings of the CCF International Conference on Natural Language
               Processing and Chinese Computing (NLPCC)},
  year      = {2026}
}
```

## Acknowledgements

We thank the authors of the TCM-SD / ZY-BERT resource for releasing the
underlying clinical data and the ZYBERT domain model that make this benchmark
possible.
