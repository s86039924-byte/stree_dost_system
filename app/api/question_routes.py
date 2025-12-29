"""Stress Dost - Acadza Question Integration Service."""
from __future__ import annotations

import json
import logging
import os
import random
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from flask import Blueprint, jsonify, request
from flask_caching import Cache

from ..services.question_mutator import mutate_question

logger = logging.getLogger(__name__)

question_bp = Blueprint("questions", __name__, url_prefix="/api/questions")
cache = Cache(config={"CACHE_TYPE": "simple"})

# Paths and API config ------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
ACADZA_API_URL = os.getenv("ACADZA_API_URL", "https://api.acadza.in/question/details")
QUESTIONS_CSV_PATH = os.getenv("QUESTION_IDS_CSV", str(BASE_DIR / "data" / "question_ids.csv"))
CACHE_TIMEOUT = 3600  # 1 hour

ACADZA_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://www.acadza.com",
    "Referer": "https://www.acadza.com/",
    "Connection": "keep-alive",
    "User-Agent": os.getenv(
        "ACADZA_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    ),
    # Defaults based on provided curl
    "api-key": os.getenv("ACADZA_API_KEY", "postmanrulz"),
    "course": os.getenv("ACADZA_COURSE", "undefined"),
}

if os.getenv("ACADZA_AUTH") is not None:
    ACADZA_HEADERS["Authorization"] = os.getenv("ACADZA_AUTH")


# CSV loader ---------------------------------------------------------------
class QuestionIDLoader:
    """Manages loading and random selection of question IDs from CSV."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.question_ids: list[str] = []
        self.load_ids()

    def load_ids(self) -> None:
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.question_ids = [row["question_id"].strip() for row in reader if row.get("question_id")]
            logger.info("Loaded %s question IDs from %s", len(self.question_ids), self.csv_path)
        except FileNotFoundError:
            logger.warning("Question ID CSV not found: %s", self.csv_path)
            self.question_ids = []
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error loading CSV %s: %s", self.csv_path, exc)
            self.question_ids = []

    def get_random_ids(self, count: int = 20) -> List[str]:
        if len(self.question_ids) <= count:
            return list(self.question_ids)
        return random.sample(self.question_ids, count)

    def get_all_ids(self) -> List[str]:
        return self.question_ids


question_loader = QuestionIDLoader(QUESTIONS_CSV_PATH)


# Acadza client ------------------------------------------------------------
class AcadzaQuestionFetcher:
    """Handles communication with Acadza API."""

    def __init__(self, api_url: str, headers: Dict):
        self.api_url = api_url
        self.headers = headers
        self.request_timeout = 10
        raw_verify = os.getenv("ACADZA_VERIFY", "true").strip().lower()
        self.verify_ssl = raw_verify not in {"0", "false", "no"}

    def fetch_question(self, question_id: str) -> Optional[Dict]:
        try:
            payload = {}
            headers = self.headers.copy()
            headers["questionId"] = question_id

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout,
                verify=self.verify_ssl,
            )

            if response.status_code == 200:
                logger.info("Fetched question: %s", question_id)
                return response.json()

            logger.warning("API returned %s for %s body=%s", response.status_code, question_id, response.text)
            return None

        except requests.Timeout:
            logger.error("Timeout fetching question %s", question_id)
            return None
        except requests.RequestException as exc:
            logger.error("Error fetching question %s: %s", question_id, exc)
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON response for question %s", question_id)
            return None

    def fetch_multiple(self, question_ids: List[str]) -> List[Dict]:
        questions: list[Dict] = []
        for qid in question_ids:
            data = self.fetch_question(qid)
            if data:
                questions.append(data)
        logger.info("Fetched %s/%s questions", len(questions), len(question_ids))
        return questions


acadza_fetcher = AcadzaQuestionFetcher(ACADZA_API_URL, ACADZA_HEADERS)


# Formatter ---------------------------------------------------------------
class QuestionFormatter:
    """Formats raw Acadza question data into frontend-ready format."""

    @staticmethod
    def format_question(raw_data: Dict, question_index: int = 0) -> Dict:
        question_type = raw_data.get("questionType", "scq")
        if question_type == "mcq":
            return QuestionFormatter._format_mcq(raw_data, question_index)
        if question_type == "integerQuestion":
            return QuestionFormatter._format_integer(raw_data, question_index)
        return QuestionFormatter._format_scq(raw_data, question_index)

    @staticmethod
    def _format_scq(raw_data: Dict, idx: int) -> Dict:
        scq_data = raw_data.get("scq", {})
        question_html = scq_data.get("question", "<p>Question not available</p>")
        options = QuestionFormatter._extract_options_from_html(question_html)
        return {
            "question_id": raw_data.get("_id", "unknown"),
            "question_index": idx + 1,
            "question_type": "scq",
            "subject": raw_data.get("subject", "Unknown"),
            "chapter": raw_data.get("chapter", "Unknown"),
            "difficulty": raw_data.get("difficulty", "Medium"),
            "level": raw_data.get("level", "MEDIUM"),
            "question_html": question_html,
            "question_images": scq_data.get("quesImages", []),
            "options": options,
            "correct_answer": scq_data.get("answer", "A"),
            "solution_html": scq_data.get("solution", "<p>Solution not available</p>"),
            "solution_images": scq_data.get("solutionImages", []),
            "metadata": {
                "smart_trick": raw_data.get("smartTrick", False),
                "trap": raw_data.get("trap", False),
                "silly_mistake": raw_data.get("sillyMistake", False),
                "is_lengthy": raw_data.get("isLengthy", 0),
                "is_ncert": raw_data.get("isNCERT", False),
                "tag_subconcepts": QuestionFormatter._extract_subconcepts(raw_data),
            },
        }

    @staticmethod
    def _format_mcq(raw_data: Dict, idx: int) -> Dict:
        mcq_data = raw_data.get("mcq", {})
        question_html = raw_data.get("scq", {}).get("question", "<p>Question not available</p>")
        return {
            "question_id": raw_data.get("_id", "unknown"),
            "question_index": idx + 1,
            "question_type": "mcq",
            "subject": raw_data.get("subject", "Unknown"),
            "chapter": raw_data.get("chapter", "Unknown"),
            "difficulty": raw_data.get("difficulty", "Medium"),
            "level": raw_data.get("level", "MEDIUM"),
            "question_html": question_html,
            "question_images": mcq_data.get("quesImages", []),
            "correct_answers": mcq_data.get("answer", []),
            "solution_html": raw_data.get("scq", {}).get("solution", "<p>Solution not available</p>"),
            "solution_images": mcq_data.get("solutionImages", []),
            "metadata": {
                "smart_trick": raw_data.get("smartTrick", False),
                "trap": raw_data.get("trap", False),
            },
        }

    @staticmethod
    def _format_integer(raw_data: Dict, idx: int) -> Dict:
        int_data = raw_data.get("integerQuestion", {})
        question_html = (
            int_data.get("question")
            or raw_data.get("scq", {}).get("question")
            or "<p>Question not available</p>"
        )
        solution_html = (
            int_data.get("solution")
            or raw_data.get("scq", {}).get("solution")
            or "<p>Solution not available</p>"
        )
        return {
            "question_id": raw_data.get("_id", "unknown"),
            "question_index": idx + 1,
            "question_type": "integer",
            "subject": raw_data.get("subject", "Unknown"),
            "chapter": raw_data.get("chapter", "Unknown"),
            "difficulty": raw_data.get("difficulty", "Medium"),
            "level": raw_data.get("level", "MEDIUM"),
            "question_html": question_html,
            "question_images": int_data.get("quesImages") or raw_data.get("scq", {}).get("quesImages", []),
            "integer_answer": int_data.get("answer"),
            "solution_html": solution_html,
            "solution_images": int_data.get("solutionImages") or raw_data.get("scq", {}).get("solutionImages", []),
            "metadata": {},
        }

    @staticmethod
    def _extract_options_from_html(html: str) -> List[Dict]:
        import re

        options: list[dict] = []
        pattern = r"\(([A-D])\)\s*(.+?)(?=\(|$)"
        matches = re.findall(pattern, html or "", re.DOTALL)
        for label, content in matches:
            clean = re.sub(r"<[^>]+>", "", content).strip()
            options.append({"label": label, "text": clean[:200]})

        if len(options) < 4:
            options = [
                {"label": "A", "text": "Option A"},
                {"label": "B", "text": "Option B"},
                {"label": "C", "text": "Option C"},
                {"label": "D", "text": "Option D"},
            ]
        return options

    @staticmethod
    def _extract_subconcepts(raw_data: Dict) -> List[str]:
        subconcepts: list[str] = []
        for tag in raw_data.get("tagSubConcept", []) or []:
            if isinstance(tag, dict) and "subConcept" in tag:
                subconcepts.append(tag["subConcept"])
        return subconcepts


# Routes -------------------------------------------------------------------
@question_bp.route("/load-test-questions", methods=["GET"])
@cache.cached(timeout=CACHE_TIMEOUT)
def load_test_questions():
    question_ids = question_loader.get_random_ids(count=20)
    if not question_ids:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "No question IDs available",
                    "questions": [],
                }
            ),
            400,
        )

    raw_questions = acadza_fetcher.fetch_multiple(question_ids)
    formatted = [QuestionFormatter.format_question(q, idx) for idx, q in enumerate(raw_questions)]

    return jsonify(
        {
            "status": "success",
            "questions": formatted,
            "total_questions": len(formatted),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@question_bp.route("/get-question/<question_id>", methods=["GET"])
@cache.cached(timeout=CACHE_TIMEOUT, query_string=True)
def get_single_question(question_id: str):
    raw_question = acadza_fetcher.fetch_question(question_id)
    if not raw_question:
        return (
            jsonify({"status": "error", "message": f"Question {question_id} not found"}),
            404,
        )

    formatted = QuestionFormatter.format_question(raw_question)
    return jsonify({"status": "success", "question": formatted})


@question_bp.route("/prefetch-batch", methods=["POST"])
def prefetch_batch():
    data = request.get_json(force=True, silent=True) or {}
    question_ids = data.get("question_ids") or []
    if not question_ids:
        return (
            jsonify({"status": "error", "message": "No question IDs provided"}),
            400,
        )

    raw_questions = acadza_fetcher.fetch_multiple(question_ids)
    formatted = [QuestionFormatter.format_question(q, idx) for idx, q in enumerate(raw_questions)]
    return jsonify({"status": "success", "questions": formatted, "prefetched_count": len(formatted)})


@question_bp.route("/stats", methods=["GET"])
def get_stats():
    return jsonify(
        {
            "total_questions_available": len(question_loader.question_ids),
            "csv_path": QUESTIONS_CSV_PATH,
            "sample_ids": question_loader.get_random_ids(5),
        }
    )


@question_bp.route("/mutate/<question_id>", methods=["POST"])
def mutate(question_id: str):
    """Mutate a question (scq/integer) by changing numeric values and answers."""
    raw_question = acadza_fetcher.fetch_question(question_id)
    if not raw_question:
        return (
            jsonify({"status": "error", "message": f"Question {question_id} not found"}),
            404,
        )

    formatted = QuestionFormatter.format_question(raw_question)
    if formatted.get("question_type") not in {"scq", "integer"}:
        return jsonify({"status": "error", "message": "Only scq/integer supported"}), 400

    mutated, changed = mutate_question(formatted)
    logger.info("mutate_endpoint question_id=%s mutated=%s", question_id, changed)
    return jsonify(
        {
            "status": "success",
            "mutated": changed,
            "question": mutated,
        }
    )


# Integration --------------------------------------------------------------
def init_question_service(app) -> None:
    cache.init_app(app)
    app.register_blueprint(question_bp)
    logger.info("Question service initialized")


__all__ = ["init_question_service"]
