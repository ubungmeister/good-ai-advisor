"""A factual overview rendered directly from validated policy records."""

from app.schemas.task_result import PolicyTaskContent


def render_policy_overview(content: PolicyTaskContent, language: str) -> str:
    if language not in {"en", "cs"}:
        raise ValueError("Unsupported policy-overview language")
    czech = language == "cs"
    lines = ["Ve smlouvě jsou zaznamenána tato krytí:" if czech else "Your policy records list these coverages:"]
    if not content.coverages:
        lines.append("- Žádná krytí nejsou v dostupných údajích uvedena." if czech
                     else "- No coverages are listed in the available records.")
    for coverage in content.coverages:
        line = f"- {coverage.coverage_type.name}"
        if coverage.limit_amount is not None:
            amount = f"{coverage.limit_amount:,.2f}"
            if czech:
                amount = amount.replace(",", " ").replace(".", ",")
            line += (": limit " + amount)
            if coverage.currency:
                line += " " + coverage.currency
        lines.append(line)
    selected = [option for option in content.options if option.selected]
    if selected:
        lines.extend(["", "Vybrané doplňky:" if czech else "Selected options:"])
        lines.extend(f"- {option.name}" + (f" ({option.variant})" if option.variant else "")
                     for option in selected)
    lines.extend(["", "Jde o přehled zaznamenaných voleb, nikoli rozhodnutí o konkrétní pojistné události."
                  if czech else "This summarizes recorded selections, not a decision on a particular claim."])
    return "\n".join(lines)
