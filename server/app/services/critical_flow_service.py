from app.schemas.safety import (
    SafetyCategory,
    SafetyDecision,
)


class CriticalFlowService:

    def handle(
        self,
        *,
        decision: SafetyDecision,
    ) -> str:

        if not decision.is_critical:
            raise ValueError(
                "CriticalFlowService received a non-critical decision."
            )

        match decision.category:

            case SafetyCategory.MEDICAL_EMERGENCY:
                return self._handle_medical_emergency()

            case SafetyCategory.PERSONAL_SAFETY:
                return self._handle_personal_safety()

            case SafetyCategory.LEGAL_EMERGENCY:
                return self._handle_legal_emergency()

            case SafetyCategory.OTHER_CRITICAL:
                return self._handle_other_critical()

            case SafetyCategory.NONE:
                raise ValueError(
                    "Critical flow cannot handle SafetyCategory.NONE."
                )

    @staticmethod
    def _handle_medical_emergency() -> str:
        return (
            "Vaše zpráva popisuje možnou akutní zdravotní situaci. "
            "V takové situaci má přednost okamžité zajištění potřebné pomoci. "
            "Informace o pojistném krytí lze řešit následně."
        )

    @staticmethod
    def _handle_personal_safety() -> str:
        return (
            "Vaše zpráva popisuje možnou bezprostřední hrozbu pro vaši bezpečnost. "
            "V takové situaci má přednost zajištění vaší osobní bezpečnosti. "
            "Informace související s pojištěním lze řešit následně."
        )

    @staticmethod
    def _handle_legal_emergency() -> str:
        return (
            "Vaše zpráva popisuje možnou urgentní právní situaci. "
            "Tento typ případu vyžaduje prioritní řešení před běžným "
            "zpracováním pojistného dotazu."
        )

    @staticmethod
    def _handle_other_critical() -> str:
        return (
            "Vaše zpráva popisuje možnou urgentní situaci. "
            "Tento případ bude zpracován prioritně před běžným "
            "pojistným dotazem."
        )