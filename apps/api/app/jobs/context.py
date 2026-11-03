"""Combine evidence once in the submitting transaction; retries retain the saved JSON."""

from app.portfolio.service import portfolio_view
from app.quant.evidence import quant_evidence
from app.research.evidence import research_evidence


def frozen_context(session, symbol, mode, cutoff, market_day, *, portfolio_snapshot=None):
    context = research_evidence(session, symbol, mode, cutoff, market_day)
    context.update(quant_evidence(session, symbol, mode, cutoff, market_day))
    if portfolio_snapshot is not None:
        context["portfolio"] = portfolio_view(session, mode, symbol, portfolio_snapshot)
    return context
