# Pencil pick-and-place → fine-tune SmolVLA → run autonomously

End-to-end workflow to teach the **SO-101** to **pick a pen off the table and place it on the black
mouse pad**, by collecting demonstrations, fine-tuning the **SmolVLA** vision-language-action model on
Kaggle's GPU, and running it autonomously.

```
 1. RECORD            2. UPLOAD            3. FINE-TUNE              4. RUN
 teleop demos   ─▶    HF Hub (auto)   ─▶   SmolVLA on Kaggle GPU ─▶  autonomous on SO-101
 (leader→follower)    dataset              (notebook)                (policy drives follower)
 + 1 camera                                  ↓ push model to Hub
```

**Why SmolVLA?** It's a compact **450M**-parameter VLA (vs ~3B for π0), so fine-tuning is **much
faster/cheaper** and fits on a free Kaggle T4 — ideal for a single task with a modest dataset.

---

## Prerequisites

- SO-101 **calibrated** (you've run `lerobot-calibrate` for `my_follower` and `my_leader`).
- **One camera** mounted with a clear, fixed view of the table, pen, and mouse pad (like your current
  overhead webcam). Its position must not change between recording and running.
- A free **Hugging Face** account (for the dataset + model) and a **Kaggle** account (for the GPU).

---

## Stage 0 — one-time setup

```bash
cd pencil_pickup_vla
cp config.env.example config.env      # then edit config.env with your values
./setup_local.sh                      # installs lerobot[feetech,dataset,smolvla] into ../.venv
hf auth login                 # paste a HF token (write scope)
./find_camera.sh                      # note your camera index -> set CAMERA_INDEX in config.env
```

Fill in `config.env`: your `HF_USER`, the two serial ports, the camera index, and keep the `TASK`
string. **The `TASK` text must be identical at record time and run time** — the policy is conditioned
on it.

---

## Stage 1 — record demonstrations

```bash
./1_record_dataset.sh
```

You teleoperate (move the **leader**, the **follower** mirrors) while the camera + joint positions are
recorded. Keyboard controls while recording:

| Key                      | Action                           |
| ------------------------ | -------------------------------- |
| **→ Right arrow** | finish this episode, go to next  |
| **← Left arrow**  | discard & re-record this episode |
| **Esc**            | stop and save                    |

**How to get a dataset that actually works** (this matters more than anything else):

- **~50 episodes** to start (set by `NUM_EPISODES`). More varied data → better policy.
- **Vary the pen's start position/orientation** every episode (left, right, near, far, angled). Also
  vary where on the pad you place it. This teaches generalization instead of one memorized trajectory.
- Keep demos **smooth and consistent** in strategy (approach → grasp → lift → move → place → release).
- Keep lighting and the camera **fixed**. Clear clutter you don't want the policy to rely on.
- During the `reset_time_s` pause, move the pen to a new spot for the next demo.

The dataset is pushed to `https://huggingface.co/datasets/<HF_USER>/so101_pencil_pickup`.
Inspect it: `lerobot-dataset-viz --repo-id=$DATASET_REPO`.

> **Your data is saved locally first.** Every episode is written to
> `~/.cache/huggingface/lerobot/<repo_id>/` *during* recording; the Hub push only happens at the end.
> So if the final push ever fails (wrong `HF_USER`, network blip…), **nothing is lost** — just run:
> ```bash
> ./recover_push_dataset.sh
> ```
> It finds your newest local dataset and pushes it to `$DATASET_REPO`.

---

## Stage 2 — get the data to Kaggle

**Option A (recommended): Hugging Face Hub.** Stage 1 already pushed the dataset to the Hub. The Kaggle
notebook just pulls it with `--dataset.repo_id` (needs *Internet ON* in the Kaggle notebook). Nothing
else to do.

**Option B: upload as a Kaggle Dataset** (if you'd rather not use the Hub on Kaggle). The recorded
dataset lives locally at `~/.cache/huggingface/lerobot/<HF_USER>/so101_pencil_pickup`:

```bash
pip install kaggle    # one-time; put your kaggle.json token in ~/.kaggle/
DS=~/.cache/huggingface/lerobot/$DATASET_REPO
kaggle datasets init -p "$DS"
# edit "$DS/dataset-metadata.json" (set a title + id), then:
kaggle datasets create -p "$DS" --dir-mode zip
```

Then attach that Kaggle dataset to the notebook and pass `--dataset.root=/kaggle/input/<your-ds>`
instead of pulling from the Hub.

---

## Stage 3 — fine-tune SmolVLA on Kaggle

Get the notebook onto Kaggle (no copy-paste) either way:
- **Web:** kaggle.com → Create → New Notebook → **File → Import Notebook → Upload** → pick
  `2_kaggle_finetune_smolvla.ipynb`.
- **Terminal:** `./push_notebook_to_kaggle.sh` (uses the Kaggle CLI + `kernel-metadata.json`, which
  pre-enables GPU + Internet). Needs a one-time `~/.kaggle/kaggle.json` token.

Then on Kaggle:

1. **Settings → Accelerator → GPU** (T4 x2 or P100), and **Internet → On**.
2. **Add-ons → Secrets** → add `HF_TOKEN` (your HF write token).
3. Edit the **Settings** cell (`HF_USER`, repo names, `BATCH_SIZE`, `STEPS`).
4. **Run all.** It installs LeRobot, fine-tunes from `lerobot/smolvla_base`, and pushes the result to
   `<HF_USER>/smolvla_pencil_pickup`.

The training command it runs (for reference):

```bash
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=$DATASET_REPO \
  --batch_size=16 --steps=20000 --save_freq=5000 \
  --output_dir=/kaggle/working/smolvla_pencil \
  --policy.device=cuda
```

**Kaggle time/GPU reality:**

- A T4 is far slower than the A100 in the docs (~4 h for 20k steps on A100). On a T4 expect it to be
  slow and possibly hit the **12 h session limit** and the **~30 h/week** GPU quota.
- So: keep `BATCH_SIZE` small (8–16, or it OOMs), **start with `STEPS=10000`** to validate the whole
  pipeline end-to-end, then do a longer run. Checkpoints every `SAVE_FREQ` let you resume.
- Watch the loss go down; for a single task, results often become usable well before 20k steps.

---

## Stage 4 — run it autonomously on the SO-101

Back on your Mac:

```bash
./3_run_autonomous.sh
```

This loads your fine-tuned model from the Hub and lets the policy drive the **follower** from the
camera + joint states — no leader. It uses the **same camera index and task string** as recording
(that's why those must match).

**Safety:** start with the workspace clear and a **hand near the power switch**. The first autonomous
runs can be jerky. If it's unsafe, kill it (Ctrl-C) — torque releases on exit (arm goes limp).

**Inference speed:** SmolVLA on a Mac (MPS/CPU, no CUDA) runs slowly, so motion may be sluggish. If the
control loop warns it's running slower than the camera FPS, that's expected without a GPU. The rollout
supports a real-time-chunking mode for low-power hardware — add these flags in `3_run_autonomous.sh`:
`--inference.type=rtc --inference.rtc.execution_horizon=10`.

---

## If the policy doesn't do the task well

1. **More & more varied data** — the #1 fix. Add episodes with new pen positions; re-record sloppy demos.
2. **Train longer** (more steps) or check the loss actually converged.
3. **Camera moved** — the policy is sensitive to viewpoint; put the camera back exactly where it was.
4. **Task string mismatch** — must be byte-for-byte the same as in the dataset.
5. **Inference too slow** → try the RTC flags above, or run inference on a CUDA machine.

## Files

| File                                | Purpose                                                               |
| ----------------------------------- | --------------------------------------------------------------------- |
| `config.env.example`              | copy to`config.env`; all your settings (ports, camera, repos, task) |
| `setup_local.sh`                  | install the LeRobot extras needed to record + run locally             |
| `find_camera.sh`                  | list cameras → get`CAMERA_INDEX`                                   |
| `1_record_dataset.sh`             | record teleoperated demos → push dataset to the Hub                  |
| `2_kaggle_finetune_smolvla.ipynb` | Kaggle GPU notebook: fine-tune SmolVLA, push model to the Hub         |
| `3_run_autonomous.sh`             | run the fine-tuned policy on the real arm                             |

## References (in the LeRobot submodule docs)

- `../lerobot/docs/source/il_robots.mdx` — recording datasets
- `../lerobot/docs/source/smolvla.mdx` — SmolVLA fine-tuning & rollout
