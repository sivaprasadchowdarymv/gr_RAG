"""
Verification Agent: check the master's answer before the user sees it.

Deterministic checks (always on, zero tokens, ~1 ms):
  citation precision   cited labels that point to real evidence
  citation coverage    factual paragraphs that carry at least one citation
  numerical grounding  every number in the answer appears in the evidence,
                       the question, or a calculator result (mA<->A etc. allowed)
  equation grounding   symbols in display equations appear in the evidence
  completeness         the answer actually answers (not empty / not cut off)

Optional LLM check (VERIFY_WITH_LLM=true, uses the "verifier" model).

These are application-level checks, not proofs of correctness.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import List, Sequence, Tuple

from config.settings import get_logger
from llm.model_router import ModelRouter
from llm.providers import LLMError
from rag.agent import NOT_FOUND

log = get_logger("verifier")

CITE = re.compile(r"\[REF-(\d+)[^\]]*\]")
_NUM = re.compile(r"(?<![A-Za-z_\d.])-?\d+(?:\.\d+)?(?![\d])")
_IDS = re.compile(r"\b(?:EQ|TBL|FIG)_\d+\b|\bREF-\d+\b|\bp\d+\b")
_DISPLAY_EQ = re.compile(r"\$\$(.+?)\$\$", re.S)
_EQ_SYMBOL = re.compile(r"\\?[A-Za-z]+(?:_\{?[A-Za-z0-9\\ ]+\}?)")


@dataclass
class VerificationReport:
    grounded: bool = True
    citation_precision: float = 1.0
    citation_coverage: float = 1.0
    numerical_score: float = 1.0
    equation_score: float = 1.0
    completeness: float = 1.0
    unsupported_claims: List[str] = field(default_factory=list)
    invalid_citations: List[str] = field(default_factory=list)
    needs_regeneration: bool = False
    llm_checked: bool = False
    notes: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def _numbers(text: str) -> List[float]:
    out = []
    for m in _NUM.findall(_IDS.sub(" ", CITE.sub(" ", text))):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out


def _supported(value: float, pool: Sequence[float]) -> bool:
    if value in (0.0, 1.0, 2.0, 3.0):  # list markers, "2 sources", trivial factors
        return True
    for p in pool:
        for scale in (1.0, 1000.0, 0.001):  # 500 mA <-> 0.5 A
            if abs(value - p * scale) <= max(1e-9, 0.005 * abs(value)):
                return True
    return False


def _norm_symbol(sym: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", sym.replace("\\", "")).upper()


def _paragraphs(answer: str) -> List[str]:
    parts = re.split(r"\n\s*\n|\n(?=\s*[-*•]\s)|\n(?=\s*\d+\.\s)", answer)
    return [p.strip() for p in parts if p.strip()]


def _is_factual(par: str) -> bool:
    plain = re.sub(r"\*\*[^*]+:\*\*", "", par).strip()
    if not plain or plain.startswith("$$") or NOT_FOUND in plain.upper():
        return False
    return bool(re.search(r"\d", plain)) or len(plain.split()) >= 8


def check(answer: str, cited_text: str, all_evidence_text: str, observations: Sequence[str], question: str,
          invalid_citations: Sequence[str]) -> VerificationReport:
    t0 = time.perf_counter()
    rep = VerificationReport(invalid_citations=list(invalid_citations))
    if not answer.strip() or NOT_FOUND in answer.upper()[:60]:
        rep.completeness = 0.0 if not answer.strip() else 1.0
        rep.latency_ms = (time.perf_counter() - t0) * 1000
        return rep

    labels = CITE.findall(answer)
    total = len(labels) + len(invalid_citations)
    rep.citation_precision = round(len(labels) / total, 3) if total else 0.0

    factual = [p for p in _paragraphs(answer) if _is_factual(p)]
    if factual:
        rep.citation_coverage = round(sum(1 for p in factual if CITE.search(p)) / len(factual), 3)

    corpus = "\n".join([all_evidence_text, *observations, question])
    pool = _numbers(corpus)
    answer_wo_math = _DISPLAY_EQ.sub(" ", answer)
    nums = _numbers(answer_wo_math)
    bad = sorted({n for n in nums if not _supported(n, pool)})
    if nums:
        rep.numerical_score = round(1 - len([n for n in nums if n in bad]) / len(nums), 3)
    for value in bad[:5]:
        txt = f"{value:g}"
        sentence = next((s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", answer_wo_math) if txt in s), txt)
        rep.unsupported_claims.append(sentence[:160])

    corpus_norm = _norm_symbol(corpus)
    symbols = [_norm_symbol(s) for eq in _DISPLAY_EQ.findall(answer) for s in _EQ_SYMBOL.findall(eq)]
    symbols = [s for s in dict.fromkeys(symbols) if len(s) >= 2 and s not in {"TIMES", "CDOT", "FRAC", "LEFT", "RIGHT"}]
    if symbols:
        rep.equation_score = round(sum(1 for s in symbols if s in corpus_norm) / len(symbols), 3)

    if len(answer.strip()) < 20 or answer.rstrip().endswith((",", " and", " the", "(")):
        rep.completeness = 0.5
    rep.grounded = (not invalid_citations and rep.numerical_score >= 0.85 and rep.equation_score >= 0.6
                    and rep.citation_precision > 0)
    rep.needs_regeneration = not rep.grounded
    rep.latency_ms = (time.perf_counter() - t0) * 1000
    return rep


def llm_check(rep: VerificationReport, answer: str, evidence_text: str, router: ModelRouter) -> VerificationReport:
    """Optional second opinion from a small model (VERIFY_WITH_LLM=true)."""
    t0 = time.perf_counter()
    prompt = ("You are a strict verifier. Compare the ANSWER with the EVIDENCE. Reply with JSON only: "
              '{"grounded": true|false, "unsupported_claims": ["..."]}.\n\n'
              f"EVIDENCE:\n{evidence_text[:4000]}\n\nANSWER:\n{answer[:2500]}")
    try:
        raw = router.chat("verifier", [{"role": "user", "content": prompt}], max_tokens=400).result.content
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        rep.llm_checked = True
        if data.get("grounded") is False:
            rep.grounded = False
            rep.needs_regeneration = True
            rep.unsupported_claims += [str(c)[:160] for c in data.get("unsupported_claims", [])][:5]
    except (LLMError, AttributeError, ValueError, TypeError) as exc:
        rep.notes.append(f"LLM verification skipped ({type(exc).__name__}).")
    rep.latency_ms += (time.perf_counter() - t0) * 1000
    return rep


def feedback_text(rep: VerificationReport) -> str:
    parts = []
    if rep.invalid_citations:
        parts.append(f"These citations do not exist: {', '.join(rep.invalid_citations)}.")
    if rep.unsupported_claims:
        parts.append("These statements contain values not found in the evidence: "
                     + " | ".join(rep.unsupported_claims[:4]))
    if rep.equation_score < 0.6:
        parts.append("Some equation symbols do not appear in the evidence; use only equations from the sources.")
    return " ".join(parts) or "Make sure every fact is supported and cited."


def canonicalize(answer: str, by_number) -> Tuple[str, list, List[str]]:
    """Rewrite citations to their true labels. Returns (answer, cited refs, invalid labels)."""
    cited, bad = [], []

    def _sub(m: "re.Match[str]") -> str:
        ref = by_number(int(m.group(1)))
        if ref is None:
            bad.append(m.group(0))
            return m.group(0)
        if ref not in cited:
            cited.append(ref)
        return ref.label

    return CITE.sub(_sub, answer), cited, list(dict.fromkeys(bad))

