"""Functions executed inside cluster pods (the benchmark payload).

The Kubeflow SDK copies each function's source text into the TrainJob;
pods run only that text. Both functions are therefore self-contained:
all imports happen inside the body, and parameters arrive as keyword
arguments (the SDK unpacks CustomTrainer func_args with **kwargs).

Pods communicate results back through "[BENCH] key=value" lines on
stdout, which bench.metrics parses from the collected pod logs.

WARNING: never use backticks or dollar signs anywhere in this file.
The SDK embeds the function source in an UNQUOTED bash heredoc, so
bash would execute backticked text as a command inside the pod.
"""


def train_func(
    model: str,
    dataset: str,
    dataset_size: int,
    batch_size: int,
    max_steps: int,
    checkpoint_dir: str | None = None,
    save_steps: int | None = None,
):
    """Fine-tune DistilBERT on an IMDB subset; print throughput markers.

    Used by scenarios 1-4. Topology (nodes/GPUs) comes from the TrainJob;
    torchrun sets RANK/WORLD_SIZE/MASTER_ADDR and HuggingFace Trainer
    picks distribution up automatically. If checkpoint_dir is set and
    contains a checkpoint (i.e. we were killed and restarted), training
    resumes from it instead of starting over.
    """
    import os

    from datasets import load_dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )
    from transformers.trainer_utils import get_last_checkpoint

    rank = int(os.environ.get("RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))

    # Fixed subset + fixed seed: every run trains on identical data.
    dataset = load_dataset(dataset, split="train").shuffle(seed=42).select(range(dataset_size))
    tokenizer = AutoTokenizer.from_pretrained(model)
    dataset = dataset.map(
        lambda batch: tokenizer(batch["text"], truncation=True, max_length=256),
        batched=True,
        remove_columns=["text"],
    )

    model = AutoModelForSequenceClassification.from_pretrained(model, num_labels=2)

    output_dir = checkpoint_dir or "/tmp/bench-output"
    training_args = TrainingArguments(
        output_dir=output_dir,
        max_steps=max_steps,
        per_device_train_batch_size=batch_size,
        save_strategy="steps" if checkpoint_dir else "no",
        save_steps=save_steps or 500,
        save_total_limit=2,
        logging_steps=25,
        report_to=[],
        seed=42,
    )

    # Resume after a pod kill: a checkpoint exists only if we ran before.
    last_checkpoint = (
        get_last_checkpoint(output_dir) if checkpoint_dir and os.path.isdir(output_dir) else None
    )
    if rank == 0 and last_checkpoint:
        print("[BENCH] resumed_from_step=" + last_checkpoint.rsplit("-", 1)[-1], flush=True)

    trainer = Trainer(
        model=model, args=training_args, train_dataset=dataset, processing_class=tokenizer
    )
    result = trainer.train(resume_from_checkpoint=last_checkpoint)

    if rank == 0:
        print("[BENCH] world_size=" + str(world_size), flush=True)
        print(
            "[BENCH] train_runtime_s=" + str(round(result.metrics["train_runtime"], 1)), flush=True
        )
        print(
            "[BENCH] train_samples_per_second="
            + str(round(result.metrics["train_samples_per_second"], 2)),
            flush=True,
        )


def hold_func(hold_s: int):
    """Occupy the requested resources for hold_s seconds, then exit.

    Used by scenarios 5-6 (gang scheduling, preemption) where only queue
    behavior is measured - no training, no package installs, so admission
    timestamps are not polluted by pip/download time.
    """
    import time

    print("[BENCH] hold_started_s=" + str(hold_s), flush=True)
    time.sleep(hold_s)
    print("[BENCH] hold_done=1", flush=True)
