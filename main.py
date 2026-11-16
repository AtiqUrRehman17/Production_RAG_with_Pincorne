"""Command-line interface for the RAG system.

Usage:
    python main.py ingest <file_path> [--user USER_ID] [--dry-run] [--show-chunks N]
    python main.py list [--user USER_ID]
    python main.py delete <document_id> [--user USER_ID]
    python main.py search "<question>" [--user USER_ID] [--doc DOCUMENT_ID] [--top-k N] [--full] [--no-rerank]
    python main.py ask "<question>" [--user USER_ID] [--doc DOCUMENT_ID] [--show-passages] [--no-rerank]
    python main.py chat [--user USER_ID] [--doc DOCUMENT_ID] [--no-rerank]
    python main.py embed-test <file_path> "<question>" [--top N]
    python main.py evaluate [--retrieval-only] [--no-rerank] [--tag NAME] [--ids q001,q002] [--limit N]
                            [--judge [METRICS]] [--deepeval [METRICS]]
    python main.py evaluate --check
    python main.py evaluate --compare TAG_A TAG_B
    python main.py evaluate --judge-run TAG [--judge METRICS] [--deepeval [METRICS]] [--tag NAME]
    python main.py evaluate --deepeval-run TAG [--deepeval METRICS] [--judge [METRICS]] [--tag NAME]
    python main.py dataset push [--dry-run] [--name NAME] [--tag VERSION_TAG]
    python main.py experiment [--retrieval-only] [--no-rerank] [--split TYPE] [--version TAG]
                              [--repetitions N] [--prefix NAME] [--name DATASET_NAME] [--judge [METRICS]]
                              [--deepeval [METRICS]]
    python main.py users
    python main.py make-admin <email> [--remove]
    python main.py move-data --from USER_ID --to <email>
"""

import argparse
import re
import sys
from pathlib import Path

from utils.exceptions import DuplicateDocumentError, RAGError


def _print_chunk(chunk) -> None:
    meta = chunk.metadata
    location = f"chunk {meta['chunk_index']}, {meta['token_count']} tokens"
    if "page_number" in meta:
        pages = meta["page_number"], meta["page_end"]
        location += f", page {pages[0]}" if pages[0] == pages[1] else f", pages {pages[0]}-{pages[1]}"
    print(f"\n{'=' * 20} {location} {'=' * 20}\n{chunk.page_content}")


def _user_id(args: argparse.Namespace) -> str:
    from utils.config import get_settings

    return args.user or get_settings().default_user_id


def cmd_ingest(args: argparse.Namespace) -> None:
    from ingestion.service import ingest_document, prepare_document
    from utils.config import get_settings

    settings = get_settings()
    user_id = _user_id(args)
    if not args.dry_run:
        record = ingest_document(Path(args.file), user_id, settings)
        print(f"\nIngested '{record.file_name}'")
        print(f"  Document ID : {record.document_id}")
        print(f"  Chunks      : {record.chunk_count} (stored in Pinecone namespace '{user_id}')")
        if record.page_count is not None:
            print(f"  Pages       : {record.page_count}")
        return

    prepared = prepare_document(Path(args.file), user_id, settings)
    file = prepared.file
    tokens = [c.metadata["token_count"] for c in prepared.chunks]
    print("\nDry run: file validated, loaded and chunked (nothing was stored)")
    print(f"  Document ID : {prepared.document_id}")
    print(f"  File        : {file.file_name} ({file.file_type}, {file.size_bytes / 1024:.1f} KB)")
    if file.page_count is not None:
        print(f"  Pages       : {file.page_count}")
    if file.encoding:
        print(f"  Encoding    : {file.encoding}")
    print(f"  Characters  : {prepared.total_chars:,}")
    print(f"  Chunks      : {len(tokens)} "
          f"(tokens min {min(tokens)} / avg {sum(tokens) // len(tokens)} / max {max(tokens)})")

    for chunk in prepared.chunks[: args.show_chunks]:
        _print_chunk(chunk)


def cmd_list(args: argparse.Namespace) -> None:
    from ingestion.service import list_documents
    from utils.config import get_settings
    from vectordb.pinecone_store import get_store

    user_id = _user_id(args)
    records = list_documents(user_id, get_settings())
    if not records:
        print(f"\nNo documents for user '{user_id}'.")
        return

    print(f"\nDocuments for user '{user_id}':\n")
    print(f"  {'DOCUMENT ID':<36}  {'TYPE':<4}  {'CHUNKS':>6}  {'UPLOADED (UTC)':<19}  FILE")
    for r in records:
        print(f"  {r.document_id:<36}  {r.file_type:<4}  {r.chunk_count:>6}  "
              f"{r.created_at[:19].replace('T', ' '):<19}  {r.file_name}")

    expected = sum(r.chunk_count for r in records)
    in_pinecone = get_store().namespace_vector_count(user_id)
    note = "" if in_pinecone == expected else "  (Pinecone stats can lag a few seconds after changes)"
    print(f"\n  {len(records)} document(s), {expected} chunks registered, "
          f"{in_pinecone} vectors in Pinecone{note}")


def cmd_delete(args: argparse.Namespace) -> None:
    from ingestion.service import delete_document
    from utils.config import get_settings

    record = delete_document(args.document_id, _user_id(args), get_settings())
    print(f"\nDeleted '{record.file_name}' ({record.document_id}) and its {record.chunk_count} chunks.")


def _retrieval_settings(args: argparse.Namespace):
    """Settings with the CLI's retrieval overrides (--no-rerank, --top-k) applied."""
    from retrieval.retriever import with_overrides
    from utils.config import get_settings

    return with_overrides(get_settings(), getattr(args, "no_rerank", False), getattr(args, "top_k", None))


def _score_label(meta: dict) -> str:
    if meta.get("score_type") == "rerank":
        return f"rerank {meta['score']:.3f} (embedding {meta['embedding_score']:.3f})"
    return f"score {meta['score']:.3f}"


def cmd_search(args: argparse.Namespace) -> None:
    from retrieval.citations import source_label
    from retrieval.retriever import DocumentRetriever

    settings = _retrieval_settings(args)
    retriever = DocumentRetriever.for_user(_user_id(args), settings, document_ids=args.doc)
    passages = retriever.invoke(args.question)

    mode = f"reranker {settings.rerank_model}" if settings.reranker_enabled else "embedding scores only"
    print(f"\nQuestion: {args.question}\nRanking:  {mode}")
    if not passages:
        print("\nNo relevant passages found.")
        return
    for i, passage in enumerate(passages, start=1):
        meta = passage.metadata
        merged = f", merged chunks {meta['chunk_index']}-{meta['chunk_index_end']}" if "chunk_index_end" in meta else ""
        print(f"\n[{i}] {_score_label(meta)}{merged} | {source_label(meta)}")
        print("-" * 70)
        print(passage.page_content if args.full else passage.page_content[:400] + ("..." if len(passage.page_content) > 400 else ""))


def _stream_to_console(token: str) -> None:
    print(token, end="", flush=True)


def _print_answer_footer(answer, show_passages: bool = False) -> None:
    print()
    if answer.standalone_question != answer.question:
        print(f"\n  (searched for: {answer.standalone_question})")
    if not answer.found:
        return
    if answer.citations:
        print("\nSources:")
        for citation in answer.citations:
            print(f"  [{citation.number}] {citation.label}")
    else:
        print("\n  Warning: the answer did not cite any source.")
    if answer.invalid_citation_numbers:
        numbers = ", ".join(f"[{n}]" for n in answer.invalid_citation_numbers)
        print(f"  Warning: the answer cited {numbers}, which do not match any source.")
    if show_passages:
        for number, passage in enumerate(answer.passages, start=1):
            print(f"\n----- source [{number}] {_score_label(passage.metadata)} -----\n{passage.page_content}")


def cmd_ask(args: argparse.Namespace) -> None:
    from llm.rag_chain import RAGChain

    chain = RAGChain(_user_id(args), _retrieval_settings(args), document_ids=args.doc)
    print()
    answer = chain.ask(args.question, on_token=_stream_to_console)
    _print_answer_footer(answer, show_passages=args.show_passages)


def cmd_chat(args: argparse.Namespace) -> None:
    import uuid

    from llm.rag_chain import ChatTurn, RAGChain
    from utils.tracing import trace_scope

    chain = RAGChain(_user_id(args), _retrieval_settings(args), document_ids=args.doc)
    history: list[ChatTurn] = []
    # LangSmith groups traces with the same thread_id into one conversation
    thread_id = str(uuid.uuid4())
    print("\nChat with your documents. Type 'exit' to quit, 'clear' to start a new conversation.")

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            return
        if question.lower() == "clear":
            history.clear()
            thread_id = str(uuid.uuid4())  # a new conversation = a new thread
            print("(conversation cleared)")
            continue

        print("\nAssistant: ", end="")
        try:
            with trace_scope(metadata={"thread_id": thread_id}):
                answer = chain.ask(question, history=history, on_token=_stream_to_console)
        except RAGError as exc:
            # Keep the chat open; the next question may work (e.g. after a rate limit)
            print(f"\nError: {exc}")
            continue
        _print_answer_footer(answer)
        history.append(ChatTurn(question, answer.text))


def cmd_embed_test(args: argparse.Namespace) -> None:
    """Embed a file's chunks and a question, then rank chunks locally (no Pinecone)."""
    import time

    from embeddings.gemini import get_embeddings
    from ingestion.service import prepare_document
    from utils.config import get_settings

    settings = get_settings()
    prepared = prepare_document(Path(args.file), settings.default_user_id, settings)
    embeddings = get_embeddings()

    started = time.perf_counter()
    chunk_vectors = embeddings.embed_documents([c.page_content for c in prepared.chunks])
    query_vector = embeddings.embed_query(args.question)
    elapsed = time.perf_counter() - started

    # Vectors are normalized, so the dot product is the cosine similarity
    scores = [sum(q * c for q, c in zip(query_vector, vec)) for vec in chunk_vectors]
    ranked = sorted(zip(scores, prepared.chunks), key=lambda pair: pair[0], reverse=True)

    print(f"\nEmbedded {len(chunk_vectors)} chunks + 1 question in {elapsed:.1f}s "
          f"({embeddings.model_name}, {len(query_vector)} dims)")
    print(f"Question: {args.question}")
    for score, chunk in ranked[: args.top]:
        marker = "" if score >= settings.min_relevance_score else "  (below MIN_RELEVANCE_SCORE)"
        print(f"\n--- score {score:.3f}{marker}")
        _print_chunk(chunk)


def _make_judge(metrics: str | None, settings):
    """The AI judge for --judge (None when the option wasn't given)."""
    if metrics is None:
        return None
    from evaluation.judge import Judge, parse_metrics

    judge = Judge(settings, parse_metrics(metrics or settings.judge_metrics))
    print(f"AI judge: {judge.label} ({', '.join(judge.metrics)})")
    return judge


_JUDGE_SHORT = {"faithfulness": "faith", "answer_relevancy": "relev",
                "context_precision": "ctx-prec", "context_recall": "ctx-rec"}


def _judge_progress(index: int, total: int, record: dict) -> None:
    scores = "  ".join(f"{_JUDGE_SHORT[name]} {value:.2f}" for name, value in record["ragas"].items())
    failed = "  (some scores failed)" if record.get("ragas_errors") else ""
    print(f"  [{index:>2}/{total}] {record['id']}  {scores or 'nothing to score'}{failed}", flush=True)


def _make_deepeval(metrics: str | None, settings):
    """The DeepEval judge for --deepeval (None when the option wasn't given)."""
    if metrics is None:
        return None
    from evaluation.deepeval_judge import DeepEvalJudge, parse_metrics

    judge = DeepEvalJudge(settings, parse_metrics(metrics or settings.deepeval_metrics))
    print(f"AI judge: {judge.label} ({', '.join(judge.metrics)}; pass mark {judge.threshold})")
    return judge


_DEEPEVAL_SHORT = {"correctness": "correct", "citation_quality": "cites",
                   "completeness": "complete", "contextual_relevancy": "ctx-rel"}


def _deepeval_progress(index: int, total: int, record: dict) -> None:
    scores = "  ".join(f"{_DEEPEVAL_SHORT[name]} {value:.2f}" for name, value in record["deepeval"].items())
    failed = "  (some scores failed)" if record.get("deepeval_errors") else ""
    print(f"  [{index:>2}/{total}] {record['id']}  {scores or 'nothing to score'}{failed}", flush=True)


def _grade(run: dict, judge, deepeval) -> None:
    """Add the AI judges' scores to an evaluation run."""
    from evaluation.deepeval_judge import deepeval_run
    from evaluation.judge import judge_run

    if judge:
        print("\nAI judge grading (RAGAS):")
        judge_run(run, judge, on_item=_judge_progress)
    if deepeval:
        print("\nAI judge grading (DeepEval):")
        deepeval_run(run, deepeval, on_item=_deepeval_progress)


def _check_tag(tag: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", tag):
        raise RAGError("--tag may only contain letters, numbers, '-' and '_' (max 40 characters).")


def cmd_evaluate(args: argparse.Namespace) -> None:
    import logging
    from collections import Counter

    from evaluation.dataset import load_dataset
    from evaluation.report import load_run, print_comparison, print_report, save_run
    from evaluation.runner import check_documents, run_evaluation

    settings = _retrieval_settings(args)
    if args.compare:
        first, second = (load_run(ref, settings.eval_results_dir) for ref in args.compare)
        print_comparison(first, second)
        return
    if not args.verbose:
        # Progress lines replace the per-step log messages
        logging.getLogger().setLevel(logging.WARNING)

    if args.judge_run and args.deepeval_run:
        raise RAGError("Use --judge-run or --deepeval-run, not both. To grade with both judges, add the "
                       "other judge's option, e.g. --judge-run TAG --deepeval.")
    saved = args.judge_run or args.deepeval_run
    if saved:
        # Grade the answers of a saved run; nothing is asked again. Scores of a judge
        # that isn't used now are kept.
        run = load_run(saved, settings.eval_results_dir)
        run["tag"] = args.tag or f"{run['tag']}-judged"[:40]
        _check_tag(run["tag"])
        print(f"\nJudging saved run '{saved}' ({run['mode']}, {len(run['results'])} questions)")
        use_ragas = bool(args.judge_run) or args.judge is not None
        use_deepeval = bool(args.deepeval_run) or args.deepeval is not None
        judge = _make_judge((args.judge or "") if use_ragas else None, settings)
        deepeval = _make_deepeval((args.deepeval or "") if use_deepeval else None, settings)
        _grade(run, judge, deepeval)
        print_report(run, show_failures=not args.no_failures)
        print(f"Saved: {save_run(run, settings.eval_results_dir)}")
        return

    dataset = load_dataset(Path(args.dataset) if args.dataset else settings.eval_dataset_path)
    user_id = args.user or settings.eval_user_id
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        dataset.items = [item for item in dataset.items if item.id in wanted]
    if args.limit:
        dataset.items = dataset.items[: args.limit]

    if args.check:
        check_documents(dataset, user_id, settings)
        types = Counter(item.type for item in dataset.items)
        print(f"\n{dataset.label} is valid: {len(dataset.items)} questions, "
              f"documents uploaded for user '{user_id}'")
        for kind, count in types.items():
            print(f"  {kind:<18}{count:>3}")
        return

    tag = args.tag or ("retrieval" if args.retrieval_only else "full") + ("-no-rerank" if args.no_rerank else "")
    _check_tag(tag)

    mode = "retrieval only" if args.retrieval_only else "full: retrieval + answers"
    print(f"\nEvaluating {dataset.label}: {len(dataset.items)} questions as user '{user_id}' ({mode})")
    # Judges are created first, so a bad setting fails before the run
    judge = _make_judge(args.judge, settings)
    deepeval = _make_deepeval(args.deepeval, settings)

    def progress(index: int, total: int, record: dict) -> None:
        if record.get("skipped"):
            status = "skip"
        elif record.get("error"):
            status = "ERR"
        elif record["passed"] is None:
            status = "n/a"
        else:
            status = "PASS" if record["passed"] else "FAIL"
        print(f"  [{index:>2}/{total}] {status:<4} {record['id']}  {record['question'][:60]}", flush=True)

    run = run_evaluation(dataset, settings, user_id, retrieval_only=args.retrieval_only,
                         tag=tag, on_item=progress)
    _grade(run, judge, deepeval)
    print_report(run, show_failures=not args.no_failures)
    print(f"Saved: {save_run(run, settings.eval_results_dir)}")


def cmd_dataset(args: argparse.Namespace) -> None:
    from evaluation.dataset import load_dataset
    from evaluation.langsmith_dataset import push_dataset
    from utils.config import get_settings

    settings = get_settings()
    dataset = load_dataset(Path(args.dataset) if args.dataset else settings.eval_dataset_path)
    name = args.name or dataset.label
    if args.tag and not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", args.tag):
        raise RAGError("--tag may only contain letters, numbers, '.', '-' and '_' (max 40 characters).")

    result = push_dataset(dataset, name, dry_run=args.dry_run, tag=args.tag)
    action = "would be" if args.dry_run else "were"
    print(f"\n{dataset.label} ({len(dataset.items)} questions) -> LangSmith dataset '{name}'"
          f"{'' if result.exists else ' (new)'}")
    print(f"  created {len(result.create)} | updated {len(result.update)} | deleted {len(result.delete)}"
          f" | unchanged {result.unchanged}")
    for label, ids in (("Created", [e["metadata"]["question_id"] for e in result.create]),
                       ("Updated", [e["metadata"]["question_id"] for e in result.update]),
                       ("Deleted", result.delete)):
        if ids and len(ids) <= 10:
            print(f"  {label}: {', '.join(ids)}")
    if result.kept:
        print(f"  Kept {result.kept} example(s) added in LangSmith itself (they have no question id)")
    if args.dry_run:
        print(f"\nDry run: nothing was uploaded. {result.changes} change(s) {action} needed.")
        return
    if not result.changes:
        print("\nAlready up to date.")
    if result.tagged:
        print(f"Tagged this version '{result.tagged}'.")
    if result.url:
        print(f"Open: {result.url}")


def cmd_experiment(args: argparse.Namespace) -> None:
    import logging

    from evaluation.dataset import QUESTION_TYPES, load_dataset
    from evaluation.deepeval_judge import METRICS as DEEPEVAL_METRICS
    from evaluation.judge import METRICS as JUDGE_METRICS
    from evaluation.langsmith_experiment import run_experiment
    from evaluation.metrics import METRICS

    settings = _retrieval_settings(args)
    dataset = load_dataset(Path(args.dataset) if args.dataset else settings.eval_dataset_path)
    name = args.name or dataset.label
    user_id = args.user or settings.eval_user_id
    unknown = [s for s in args.split or () if s not in QUESTION_TYPES]
    if unknown:
        raise RAGError(f"Unknown --split {', '.join(unknown)} (allowed: {', '.join(QUESTION_TYPES)})")
    if args.prefix and not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", args.prefix):
        raise RAGError("--prefix may only contain letters, numbers, '.', '-' and '_' (max 40 characters).")
    if not 1 <= args.repetitions <= 5:
        raise RAGError("--repetitions must be between 1 and 5.")
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)

    mode = "retrieval only" if args.retrieval_only else f"full: answers by {settings.llm_provider} {settings.llm_model}"
    print(f"\nLangSmith experiment on dataset '{name}' (version {args.version or 'latest'}) "
          f"as user '{user_id}' ({mode})")
    judge = _make_judge(args.judge, settings)
    deepeval = _make_deepeval(args.deepeval, settings)

    def progress(index: int, total: int, example, feedback: dict) -> None:
        if "error" in feedback:
            status = "ERR"
        elif feedback.get("passed") is None or feedback["passed"].score is None:
            status = "n/a"
        else:
            status = "PASS" if feedback["passed"].score else "FAIL"
        question_id = (example.metadata or {}).get("question_id", "?")
        print(f"  [{index:>2}/{total}] {status:<4} {question_id}  {example.inputs['question'][:60]}", flush=True)

    result = run_experiment(
        dataset, name, settings, user_id, retrieval_only=args.retrieval_only, splits=args.split,
        version=args.version, repetitions=args.repetitions, prefix=args.prefix, judge=judge,
        deepeval=deepeval, on_result=progress,
    )

    print(f"\nEXPERIMENT {result.name}")
    if result.skipped:
        print(f"  ({result.skipped} question(s) skipped: they can only be judged in a full run)")
    for key, label, kind in METRICS:
        value = result.average(key)
        if value is not None:
            shown = f"{value:.3f}" if kind == "score" else f"{value * 100:.1f}%"
            print(f"  {label:<28}{shown:>10}   (n={len(result.scores[key])})")
    if judge:
        print(f"\nAI JUDGE ({judge.label})")
        for key, label in JUDGE_METRICS:
            value = result.average(f"ragas_{key}")
            if value is not None:
                print(f"  {label:<28}{value:>10.3f}   (n={len(result.scores[f'ragas_{key}'])})")
    if deepeval:
        print(f"\nAI JUDGE ({deepeval.label}, pass mark {deepeval.threshold})")
        for key, label in DEEPEVAL_METRICS:
            values = result.scores.get(f"deepeval_{key}")
            if values:
                passed_checks = sum(v >= deepeval.threshold for v in values)
                print(f"  {label:<28}{result.average(f'deepeval_{key}'):>10.3f}   "
                      f"passed {passed_checks} / {len(values)}")
        print("  (the judge's reason for each score is the comment on the deepeval_* columns in LangSmith)")
    for used in (judge, deepeval):
        if used and used.stopped:
            print(f"  WARNING ({used.label}): {used.stopped}.")
    passed = result.scores.get("passed", [])
    print(f"\nPASSED  {int(sum(passed))} / {len(passed)} questions")
    if result.errors:
        print(f"  WARNING: {result.errors} question(s) could not run; see the error column in LangSmith.")
    if result.url:
        print(f"Open: {result.url}")


def cmd_users(args: argparse.Namespace) -> None:
    from accounts.service import list_users

    users = list_users()
    if not users:
        print("\nNo accounts yet. Register one through the API: POST /api/v1/auth/register")
        return
    print(f"\n  {'ACCOUNT ID (use as --user)':<36}  {'ROLE':<5}  {'ACTIVE':<6}  {'CREATED (UTC)':<16}  EMAIL")
    for user in users:
        print(f"  {user.id:<36}  {user.role:<5}  {'yes' if user.is_active else 'no':<6}  "
              f"{user.created_at:%Y-%m-%d %H:%M}  {user.email}")
    print(f"\n  {len(users)} account(s)")


def cmd_make_admin(args: argparse.Namespace) -> None:
    from accounts.service import set_role

    user = set_role(args.email, "user" if args.remove else "admin")
    print(f"\n{user.email} is now {'a normal user' if args.remove else 'an admin'}. "
          "(Takes effect at the next login or token refresh.)")


def cmd_move_data(args: argparse.Namespace) -> None:
    from accounts.service import find_user, transfer_user_data
    from utils.config import get_settings

    user = find_user(args.to)
    if user is None:
        raise RAGError(f"No account with the email {args.to}. Register it first.")
    result = transfer_user_data(args.from_user, user.id, get_settings())
    print(f"\nMoved from '{args.from_user}' to {user.email}: {result['documents_moved']} document(s), "
          f"{result['conversations_moved']} conversation(s)."
          + (f" {result['documents_skipped']} document(s) were already in that account and were left."
             if result["documents_skipped"] else ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag", description="Chat with your documents.")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Upload a PDF, DOCX or TXT file")
    ingest.add_argument("file", help="Path to the file")
    ingest.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    ingest.add_argument(
        "--dry-run", action="store_true",
        help="Only validate, load and chunk the file; don't store anything",
    )
    ingest.add_argument(
        "--show-chunks", type=int, default=3, metavar="N",
        help="With --dry-run: print the first N chunks (default 3)",
    )
    ingest.set_defaults(handler=cmd_ingest)

    list_cmd = commands.add_parser("list", help="List your uploaded documents")
    list_cmd.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    list_cmd.set_defaults(handler=cmd_list)

    delete = commands.add_parser("delete", help="Delete a document and its chunks")
    delete.add_argument("document_id", help="ID shown by the 'list' command")
    delete.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    delete.set_defaults(handler=cmd_delete)

    search = commands.add_parser("search", help="Find the passages most relevant to a question")
    search.add_argument("question", help="Your question")
    search.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    search.add_argument(
        "--doc", action="append", metavar="DOCUMENT_ID",
        help="Only search this document (repeat to search several)",
    )
    search.add_argument("--top-k", type=int, help="Most passages to return (defaults to RERANK_TOP_N / TOP_K in .env)")
    search.add_argument("--full", action="store_true", help="Print full passages")
    search.add_argument("--no-rerank", action="store_true", help="Rank by embedding scores only (for comparison)")
    search.set_defaults(handler=cmd_search)

    ask = commands.add_parser("ask", help="Ask one question and get a cited answer")
    ask.add_argument("question", help="Your question")
    ask.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    ask.add_argument("--doc", action="append", metavar="DOCUMENT_ID", help="Only use this document (repeatable)")
    ask.add_argument("--show-passages", action="store_true", help="Also print the passages sent to the LLM")
    ask.add_argument("--no-rerank", action="store_true", help="Rank by embedding scores only (for comparison)")
    ask.set_defaults(handler=cmd_ask)

    chat = commands.add_parser("chat", help="Have a conversation with your documents")
    chat.add_argument("--user", help="User ID (defaults to DEFAULT_USER_ID in .env)")
    chat.add_argument("--doc", action="append", metavar="DOCUMENT_ID", help="Only use this document (repeatable)")
    chat.add_argument("--no-rerank", action="store_true", help="Rank by embedding scores only (for comparison)")
    chat.set_defaults(handler=cmd_chat)

    embed_test = commands.add_parser(
        "embed-test", help="Rank a file's chunks against a question using embeddings only"
    )
    embed_test.add_argument("file", help="Path to the file")
    embed_test.add_argument("question", help="Question to compare against the chunks")
    embed_test.add_argument("--top", type=int, default=3, help="How many chunks to show")
    embed_test.set_defaults(handler=cmd_embed_test)

    evaluate = commands.add_parser("evaluate", help="Run the golden dataset and score the system")
    evaluate.add_argument("--dataset", help="Dataset file (defaults to EVAL_DATASET_PATH in .env)")
    evaluate.add_argument("--user", help="User whose documents are searched (defaults to EVAL_USER_ID)")
    evaluate.add_argument("--retrieval-only", action="store_true",
                          help="Only score retrieval (no LLM answers; cheaper and faster)")
    evaluate.add_argument("--no-rerank", action="store_true", help="Evaluate with embedding scores only")
    evaluate.add_argument("--tag", help="Name for this run, used to compare runs later")
    evaluate.add_argument("--ids", help="Only these question ids, comma-separated (e.g. q001,q020)")
    evaluate.add_argument("--limit", type=int, help="Only the first N questions")
    evaluate.add_argument("--check", action="store_true",
                          help="Only validate the dataset and its documents (no API calls)")
    evaluate.add_argument("--compare", nargs=2, metavar=("A", "B"),
                          help="Compare two saved runs (tags or result files)")
    evaluate.add_argument("--no-failures", action="store_true", help="Don't list failed questions")
    evaluate.add_argument("--judge", nargs="?", const="", metavar="METRICS",
                          help="Also grade answers with the AI judge (RAGAS). Optionally a comma-separated "
                               "list, e.g. faithfulness,answer_relevancy (defaults to JUDGE_METRICS)")
    evaluate.add_argument("--judge-run", metavar="TAG",
                          help="Grade a saved run with the AI judge (no new answers; saved as TAG-judged)")
    evaluate.add_argument("--deepeval", nargs="?", const="", metavar="METRICS",
                          help="Also grade answers with DeepEval checks (with reasons). Optionally a comma-separated "
                               "list, e.g. correctness,completeness (defaults to DEEPEVAL_METRICS)")
    evaluate.add_argument("--deepeval-run", metavar="TAG",
                          help="Grade a saved run with DeepEval (no new answers; saved as TAG-judged)")
    evaluate.add_argument("--verbose", action="store_true", help="Keep the per-step log messages")
    evaluate.set_defaults(handler=cmd_evaluate)

    dataset = commands.add_parser("dataset", help="Upload the golden dataset to LangSmith")
    dataset.add_argument("action", choices=["push"], help="push: make the LangSmith dataset match the file")
    dataset.add_argument("--dataset", help="Dataset file (defaults to EVAL_DATASET_PATH in .env)")
    dataset.add_argument("--name", help="LangSmith dataset name (defaults to the dataset label, e.g. golden_v1)")
    dataset.add_argument("--tag", help="Name this dataset version (e.g. v1) so experiments can refer to it")
    dataset.add_argument("--dry-run", action="store_true", help="Show what would change; upload nothing")
    dataset.set_defaults(handler=cmd_dataset)

    experiment = commands.add_parser(
        "experiment", help="Run the LangSmith dataset as an experiment (scores shown in LangSmith)"
    )
    experiment.add_argument("--dataset", help="Local dataset file (defaults to EVAL_DATASET_PATH in .env)")
    experiment.add_argument("--name", help="LangSmith dataset name (defaults to the dataset label, e.g. golden_v1)")
    experiment.add_argument("--user", help="User whose documents are searched (defaults to EVAL_USER_ID)")
    experiment.add_argument("--retrieval-only", action="store_true",
                            help="Only score retrieval (no LLM answers; cheaper and faster)")
    experiment.add_argument("--no-rerank", action="store_true", help="Rank by embedding scores only")
    experiment.add_argument("--split", action="append", metavar="TYPE",
                            help="Only questions of this type, e.g. table (repeat for several)")
    experiment.add_argument("--version", metavar="TAG",
                            help="Dataset version tag to run, e.g. v1 (defaults to the latest version)")
    experiment.add_argument("--repetitions", type=int, default=1,
                            help="Run every question N times to see how stable the answers are (default 1)")
    experiment.add_argument("--prefix", help="Start of the experiment name (defaults to the mode and provider)")
    experiment.add_argument("--judge", nargs="?", const="", metavar="METRICS",
                            help="Also grade with the AI judge (RAGAS); scores appear as ragas_* columns")
    experiment.add_argument("--deepeval", nargs="?", const="", metavar="METRICS",
                            help="Also grade with DeepEval; scores appear as deepeval_* columns, "
                                 "with the judge's reason as the comment")
    experiment.add_argument("--verbose", action="store_true", help="Keep the per-step log messages")
    experiment.set_defaults(handler=cmd_experiment)

    users = commands.add_parser("users", help="List the accounts registered through the API")
    users.set_defaults(handler=cmd_users)

    make_admin = commands.add_parser("make-admin", help="Give an account admin rights (logs, traces, evaluations)")
    make_admin.add_argument("email", help="The account's email")
    make_admin.add_argument("--remove", action="store_true", help="Take admin rights away instead")
    make_admin.set_defaults(handler=cmd_make_admin)

    move_data = commands.add_parser("move-data", help="Give one user's documents and chats to an account")
    move_data.add_argument("--from", dest="from_user", required=True, metavar="USER_ID",
                           help="Current owner, e.g. local-user")
    move_data.add_argument("--to", required=True, metavar="EMAIL", help="The account that receives them")
    move_data.set_defaults(handler=cmd_move_data)

    return parser


# Commands whose work is recorded as LangSmith traces
_TRACED_COMMANDS = {"ingest", "search", "ask", "chat", "evaluate", "embed-test"}


def _trace_labels(args: argparse.Namespace) -> tuple[list[str], dict]:
    """Tags and metadata added to every trace this command produces."""
    from utils.tracing import model_labels

    settings = _retrieval_settings(args)
    default_user = settings.eval_user_id if args.command == "evaluate" else settings.default_user_id
    metadata = {"user_id": getattr(args, "user", None) or default_user, **model_labels(settings)}
    return [args.command], metadata


def main() -> int:
    # Windows terminals default to a legacy encoding that can't print all characters
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Importing the settings loads .env into the environment, so LangSmith sees
    # its settings before any LangChain code runs
    from utils.tracing import flush_traces, trace_scope, tracing_enabled, tracing_project

    args = build_parser().parse_args()
    traced_run = (
        args.command in _TRACED_COMMANDS
        and not getattr(args, "check", False)
        and not getattr(args, "compare", None)
        and tracing_enabled()
    )
    try:
        tags, metadata = _trace_labels(args) if traced_run else ([], {})
        with trace_scope(tags=tags, metadata=metadata):
            args.handler(args)
    except DuplicateDocumentError as exc:
        print(f"\nSkipped: {exc} (document ID: {exc.existing_document_id})")
    except RAGError as exc:
        print(f"\nError: {exc}")
        return 1
    finally:
        flush_traces()
    if traced_run:
        print(f"\n(Traced in LangSmith project '{tracing_project()}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
