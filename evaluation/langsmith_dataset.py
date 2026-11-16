"""Upload (sync) a golden dataset to LangSmith, so the answer key lives next to
the traces and LangSmith experiments can run over it.

The JSON file stays the master copy: edit it, then push again. Each question
becomes one LangSmith example, matched by its question id, so pushing again
creates the new questions, updates the changed ones, deletes the ones removed
from the file and leaves the rest alone. It never creates duplicates.

  inputs   what the system receives: the question and the chat history
  outputs  the answer key: answerable, expected answer, key facts, sources
  metadata question id, type and dataset label (for filtering)
  split    the question type, so one kind of question can be run on its own
"""

import os
from dataclasses import dataclass, field

from evaluation.dataset import Dataset, EvalItem, ExpectedSource, HistoryTurn
from utils.exceptions import LangSmithError
from utils.logger import get_logger

logger = get_logger(__name__)

# LangSmith stores an example's split in its metadata under this key
_SPLIT_KEY = "dataset_split"


def _source(source: ExpectedSource) -> dict:
    return {key: value for key, value in
            (("file", source.file), ("section", source.section), ("page", source.page))
            if value is not None}


def to_example(item: EvalItem, dataset: Dataset) -> dict:
    """One golden question as a LangSmith example."""
    metadata = {"question_id": item.id, "type": item.type, "dataset": dataset.label}
    if item.notes:
        metadata["notes"] = item.notes
    return {
        "inputs": {
            "question": item.question,
            "history": [{"question": t.question, "answer": t.answer} for t in item.history],
        },
        "outputs": {
            "answerable": item.answerable,
            "expected_answer": item.expected_answer,
            "key_facts": [list(options) for options in item.key_facts],
            "expected_sources": [_source(s) for s in item.expected_sources],
            "also_acceptable": [_source(s) for s in item.also_acceptable],
        },
        "metadata": metadata,
        "split": item.type,
    }


def from_example(example) -> EvalItem:
    """A LangSmith example back as a golden question (the reverse of to_example)."""
    inputs, outputs, metadata = example.inputs, example.outputs or {}, example.metadata or {}
    return EvalItem(
        id=metadata.get("question_id") or str(example.id),
        question=inputs["question"],
        type=metadata.get("type", "clear"),
        answerable=outputs.get("answerable", True),
        expected_answer=outputs.get("expected_answer"),
        key_facts=tuple(tuple(options) for options in outputs.get("key_facts", [])),
        expected_sources=tuple(ExpectedSource(**s) for s in outputs.get("expected_sources", [])),
        also_acceptable=tuple(ExpectedSource(**s) for s in outputs.get("also_acceptable", [])),
        history=tuple(HistoryTurn(t["question"], t["answer"]) for t in inputs.get("history", [])),
        notes=metadata.get("notes", ""),
    )


def _matches(existing, wanted: dict) -> bool:
    metadata = dict(existing.metadata or {})
    split = metadata.pop(_SPLIT_KEY, None)
    return (
        existing.inputs == wanted["inputs"]
        and existing.outputs == wanted["outputs"]
        and metadata == wanted["metadata"]
        and split in (wanted["split"], [wanted["split"]])
    )


@dataclass
class SyncResult:
    name: str
    exists: bool
    create: list[dict] = field(default_factory=list)
    update: list[dict] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)  # question ids
    unchanged: int = 0
    kept: int = 0  # examples added in LangSmith itself (no question id): left alone
    url: str | None = None
    tagged: str | None = None

    @property
    def changes(self) -> int:
        return len(self.create) + len(self.update) + len(self.delete)


def langsmith_client():
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise LangSmithError("LANGSMITH_API_KEY is not set in .env, so LangSmith can't be used.")
    from langsmith import Client

    return Client()


def push_dataset(dataset: Dataset, name: str, dry_run: bool = False, tag: str | None = None) -> SyncResult:
    """Make the LangSmith dataset `name` match the golden dataset file."""
    client = langsmith_client()
    try:
        exists = client.has_dataset(dataset_name=name)
        existing_examples = list(client.list_examples(dataset_name=name)) if exists else []
    except Exception as exc:
        raise LangSmithError(f"Could not read dataset '{name}' from LangSmith: {exc}") from exc

    result = SyncResult(name=name, exists=exists)
    by_question: dict[str, object] = {}
    duplicates = []
    for example in existing_examples:
        question_id = (example.metadata or {}).get("question_id")
        if not question_id:
            result.kept += 1
        elif question_id in by_question:
            duplicates.append(example)  # e.g. a copy made in the LangSmith UI
        else:
            by_question[question_id] = example

    wanted_ids = set()
    for item in dataset.items:
        wanted = to_example(item, dataset)
        wanted_ids.add(item.id)
        example = by_question.get(item.id)
        if example is None:
            result.create.append(wanted)
        elif _matches(example, wanted):
            result.unchanged += 1
        else:
            result.update.append({**wanted, "id": example.id})
    stale = [e for qid, e in by_question.items() if qid not in wanted_ids] + duplicates
    result.delete = [(e.metadata or {}).get("question_id") for e in stale]

    if dry_run:
        return result

    try:
        if exists:
            remote = client.read_dataset(dataset_name=name)
        else:
            remote = client.create_dataset(
                name, description=dataset.description,
                metadata={"source_file": dataset.path.name if dataset.path else None, "label": dataset.label},
            )
        if result.create:
            client.create_examples(dataset_id=remote.id, examples=result.create)
        if result.update:
            client.update_examples(dataset_id=remote.id, updates=result.update)
        if stale:
            client.delete_examples([e.id for e in stale])
        # Changes create a new dataset version; a tag names it for experiments.
        # A tag must point at an existing version's exact time, so tag the latest one.
        if tag:
            latest = client.read_dataset_version(dataset_id=remote.id, tag="latest")
            client.update_dataset_tag(dataset_id=remote.id, as_of=latest.as_of, tag=tag)
            result.tagged = tag
    except Exception as exc:
        raise LangSmithError(f"Uploading dataset '{name}' to LangSmith failed: {exc}") from exc

    result.url = remote.url
    logger.info("LangSmith dataset '%s': %d created, %d updated, %d deleted, %d unchanged",
                name, len(result.create), len(result.update), len(result.delete), result.unchanged)
    return result
