from app.schemas.safety import (
    SafetyDecision,
    SafetyRoute,
)


class SafetyRouter:

    def route(
        self,
        *,
        decision: SafetyDecision,
    ) -> SafetyRoute:

        if decision.is_critical:
            return SafetyRoute.CRITICAL_FLOW

        return SafetyRoute.NORMAL_FLOW