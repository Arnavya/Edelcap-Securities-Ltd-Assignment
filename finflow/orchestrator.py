"""End-to-end orchestration.

Implements the linear learning loop:
  question -> retrieve -> V1 -> gap -> learning event -> memory
          -> retrieve(+learned context) -> V2 -> (P7) evaluation

Train cycle (``run_learning_cycle``) generates a learning event and re-runs the same
question with it. Held-out cycle (``run_heldout``) re-runs a twin using its family's
learned patterns WITHOUT generating its own — the generalization test. Both record
``newly_retrieved_ids`` / ``newly_cited_ids`` for P7's anti-memorization gates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .agents import GapAnalysisAgent, InvestigationAgent, LearningEventGenerator
from .config import Settings, load_settings
from .llm import LLMProvider, build_provider
from .memory import LearnedContext, LearningMemory
from .models import Answer, AnswerVersion, GapAnalysis, Question, RetrievalSnapshot, RunRecord
from .persistence import Repository, SQLiteRepository
from .retrieval import BM25Retriever, KnowledgeStore, Retriever


def _new_ids(v2: list[str], v1: list[str]) -> list[str]:
    seen = set(v1)
    return [x for x in v2 if x not in seen]


class Orchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        store: KnowledgeStore,
        retriever: Retriever,
        repo: Repository,
        *,
        retrieval_k: int = 4,
    ) -> None:
        self.store = store
        self.repo = repo
        self.retrieval_k = retrieval_k
        self.investigator = InvestigationAgent(provider, retriever, store)
        self.gap_agent = GapAnalysisAgent(provider)
        self.learner = LearningEventGenerator(provider, store)
        self.memory = LearningMemory(repo)

    @classmethod
    def build(cls, settings: Settings | None = None) -> "Orchestrator":
        settings = settings or load_settings()
        store = KnowledgeStore.from_dir()
        return cls(
            provider=build_provider(settings),
            store=store,
            retriever=BM25Retriever(store.all()),
            repo=SQLiteRepository.from_settings(settings),
            retrieval_k=settings.retrieval_k,
        )

    # --- V1 ---
    def run_v1(self, question: Question, *, persist: bool = True) -> RunRecord:
        answer, snapshot = self.investigator.investigate(
            question, version=AnswerVersion.V1, k_per_source=self.retrieval_k
        )
        run = RunRecord(
            run_id=f"{question.id}-v1-{uuid4().hex[:8]}",
            question_id=question.id,
            phase="baseline_train",
            v1=answer,
            retrieval_v1=snapshot,
            human=self.repo.get_human_answer(question.id),
            created_at=datetime.now(timezone.utc),
        )
        if persist:
            self.repo.save_question(question)
            self.repo.save_answer(run.run_id, answer)
            self.repo.save_retrieval_snapshot(run.run_id, snapshot)
            self.repo.save_run(run)
        return run

    # --- gap ---
    def add_gap_analysis(self, run: RunRecord, *, persist: bool = True) -> GapAnalysis:
        if run.v1 is None:
            raise ValueError("run has no V1 answer to analyze")
        human = run.human or self.repo.get_human_answer(run.question_id)
        if human is None:
            raise ValueError(f"no human answer for {run.question_id}; cannot run gap analysis")
        question = self.repo.get_question(run.question_id)
        if question is None:
            raise ValueError(f"question {run.question_id} not persisted")
        gap = self.gap_agent.analyze(question, run.v1, human)
        run.gap = gap
        run.human = human
        if persist:
            self.repo.save_gap_analysis(run.run_id, gap)
            self.repo.save_run(run)
        return gap

    # --- V2 (memory-augmented) ---
    def _investigate_v2(self, question: Question, context: LearnedContext) -> tuple[Answer, RetrievalSnapshot]:
        return self.investigator.investigate(
            question,
            version=AnswerVersion.V2,
            k_per_source=self.retrieval_k,
            expansion_terms=context.expansion_terms,
            routing_sources=context.routing_sources,
            guidance_text=context.guidance_text,
            injected_pattern_ids=context.pattern_ids,
        )

    def run_ablation(self, question: Question) -> tuple[Answer, RetrievalSnapshot]:
        """V2 machinery with the learned context STRIPPED — attribution control."""
        return self.investigator.investigate(question, version=AnswerVersion.V2, k_per_source=self.retrieval_k)

    # --- full train cycle: V1 -> gap -> learn -> V2 (same question) ---
    def run_learning_cycle(self, question: Question, *, persist: bool = True) -> RunRecord:
        human = self.repo.get_human_answer(question.id)
        if human is None:
            raise ValueError(f"no human answer for {question.id}")

        v1, snap_v1 = self.investigator.investigate(question, version=AnswerVersion.V1, k_per_source=self.retrieval_k)
        gap = self.gap_agent.analyze(question, v1, human)
        event = self.learner.generate(question, v1, gap, human)
        self.memory.store(event)

        context = self.memory.context_for(question)
        v2, snap_v2 = self._investigate_v2(question, context)
        snap_v2.diagnostics.notes.extend(context.diagnostic_notes())

        run = RunRecord(
            run_id=f"{question.id}-cycle-{uuid4().hex[:8]}",
            question_id=question.id,
            phase="v2_train",
            v1=v1, v2=v2,
            retrieval_v1=snap_v1, retrieval_v2=snap_v2,
            human=human, gap=gap, learning_event=event,
            newly_retrieved_ids=_new_ids(snap_v2.source_ids, snap_v1.source_ids),
            newly_cited_ids=_new_ids(v2.cited_source_ids, v1.cited_source_ids),
            created_at=datetime.now(timezone.utc),
        )
        if persist:
            self._persist_run(run, question, event=event, gap=gap)
        return run

    # --- held-out twin: V1 baseline, then V2 using the family's learned patterns ---
    def run_heldout(self, question: Question, *, persist: bool = True) -> RunRecord:
        human = self.repo.get_human_answer(question.id)

        v1, snap_v1 = self.investigator.investigate(question, version=AnswerVersion.V1, k_per_source=self.retrieval_k)
        # Use the family's patterns but never the held-out question's own event.
        context = self.memory.context_for(question, exclude_question_ids={question.id})
        v2, snap_v2 = self._investigate_v2(question, context)
        snap_v2.diagnostics.notes.extend(context.diagnostic_notes())

        run = RunRecord(
            run_id=f"{question.id}-heldout-{uuid4().hex[:8]}",
            question_id=question.id,
            phase="post_learning_heldout",
            v1=v1, v2=v2,
            retrieval_v1=snap_v1, retrieval_v2=snap_v2,
            human=human,
            newly_retrieved_ids=_new_ids(snap_v2.source_ids, snap_v1.source_ids),
            newly_cited_ids=_new_ids(v2.cited_source_ids, v1.cited_source_ids),
            created_at=datetime.now(timezone.utc),
        )
        # The patterns applied to V2 are recorded on v2.injected_pattern_ids.
        if persist:
            self._persist_run(run, question)
        return run

    def _persist_run(self, run: RunRecord, question: Question, *, event=None, gap=None) -> None:
        self.repo.save_question(question)
        if run.v1 is not None:
            self.repo.save_answer(run.run_id, run.v1)
            if run.retrieval_v1:
                self.repo.save_retrieval_snapshot(run.run_id, run.retrieval_v1)
        if run.v2 is not None:
            self.repo.save_answer(run.run_id, run.v2)
            if run.retrieval_v2:
                self.repo.save_retrieval_snapshot(run.run_id, run.retrieval_v2)
        if gap is not None:
            self.repo.save_gap_analysis(run.run_id, gap)
        if event is not None:
            self.repo.save_learning_event(event)
        self.repo.save_run(run)
