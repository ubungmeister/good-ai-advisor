"""Time a synthetic copy of the broad policy overview through the real AI stages."""

import argparse
import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from time import perf_counter
from uuid import UUID


class TimedLLM:
    def __init__(self, target):
        self.target = target
        self.stages = []

    async def _call(self, method, stage, kwargs):
        started = perf_counter()
        row = {"stage": stage}
        try:
            result = await getattr(self.target, method)(**kwargs)
            row["status"] = "completed"
            row["output_characters"] = len(result if isinstance(result, str) else result.model_dump_json())
            return result
        except Exception as exc:
            row.update(status="error", error_type=type(exc).__name__)
            raise
        finally:
            row["seconds"] = round(perf_counter() - started, 3)
            self.stages.append(row)

    async def generate_answer(self, **kwargs):
        return await self._call("generate_answer", "answer_generation", kwargs)

    async def generate_structured(self, **kwargs):
        return await self._call("generate_structured", kwargs["response_model"].__name__, kwargs)


def overview_fixture():
    from app.schemas.task_result import PolicyTaskContent
    from scripts.ai_eval_fixtures import policy_fixture

    payload = policy_fixture().model_dump(mode="json")
    for index, (code, name, limit) in enumerate([
        ("ASSISTANCE", "Assistance Services", None),
        ("LIABILITY", "Liability", "20000000.00"),
        ("MEDICAL_EXPENSES", "Medical Expenses", "100000000.00"),
    ], 100):
        payload["coverages"].append({"id": str(UUID(int=index)), "limit_amount": limit,
            "currency": "CZK" if limit else None, "coverage_type": {"code": code, "name": name}})
    payload["options"] = [{"id": str(UUID(int=index)), "code": code, "name": name,
        "selected": selected, "variant": variant, "currency": None}
        for index, (code, name, selected, variant) in enumerate([
            ("CANCELLATION", "Trip Cancellation", True, "STANDARD"),
            ("VEHICLE_ASSISTANCE", "Vehicle Assistance", False, None),
            ("WINTER_SPORTS", "Winter Sports", True, None),
        ], 200)]
    payload["people"] = [{"role": "POLICYHOLDER", "person": {
        "id": str(UUID(int=300)), "first_name": "Eval", "last_name": "Person"}}]
    payload["travel_details"] = {"coverage_mode": "SINGLE_TRIP", "territory": "EUROPE",
        "destination_country_code": "DE", "trip_purpose": "LEISURE", "sport_level": "RECREATIONAL"}
    return PolicyTaskContent.model_validate(payload)


async def run(args):
    from app.core.config import settings
    from app.core.dependencies import get_llm_service, get_response_validator
    from scripts.ai_eval_fixtures import FixturePolicyService, FixtureRetrieval, USER_ID, POLICY_ID
    from scripts.run_ai_eval import build_chat
    from app.services.policy_overview import render_policy_overview

    class OverviewPolicy(FixturePolicyService):
        def get_policy_details_for_user(self, **kwargs):
            return overview_fixture()

    llm = get_llm_service()
    rows = []
    for index in range(args.runs):
        timed = TimedLLM(llm)
        validator = get_response_validator()
        validator.grounding_validator.llm_service = timed
        service, observers = build_chat(timed, validator, OverviewPolicy(), FixtureRetrieval([]))
        row = {"run": index + 1}
        started = perf_counter()
        try:
            with redirect_stdout(io.StringIO()):
                answer, _ = await asyncio.wait_for(service.generate_answer(
                    db=None, message="What insurance do I have?", user_id=USER_ID, policy_id=POLICY_ID,
                ), timeout=60)
            validations = observers["validator"].calls
            templated = answer == render_policy_overview(overview_fixture(), "en")
            row.update(status="completed", answer=answer, words=len(answer.split()),
                validator_action=validations[-1].get("output", {}).get("action") if validations else None,
                answer_path="recorded_policy_template" if templated else "generated_or_fallback",
                matches_fixture_template=templated,
                validations=[call.get("output") for call in validations])
        except Exception as exc:
            row.update(status="error", error_type=type(exc).__name__)
        row.update(seconds=round(perf_counter() - started, 3), stages=timed.stages)
        rows.append(row)
        args.output.write_text(json.dumps({"question": "What insurance do I have?",
            "synthetic_policy": overview_fixture().model_dump(mode="json"),
            "provider": settings.llm_provider,
            "model": settings.gemini_model if settings.llm_provider == "gemini" else settings.groq_model,
            "runs": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in row.items() if key != "answer"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.runs <= 5:
        parser.error("Use a new output path and between one and five runs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
