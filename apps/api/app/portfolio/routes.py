from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.http.dependencies import SessionDep
from app.portfolio.schemas import CsvPreview, PositionImport, PositionInput
from app.portfolio.service import (
    CSV_COLUMNS,
    delete_lot,
    import_lots,
    portfolio_view,
    preview_csv,
    update_lot,
)

router = APIRouter(prefix="/api")


@router.get("/portfolio")
def holdings(request: Request, session: SessionDep):
    return portfolio_view(session, request.app.state.settings.market_provider)


@router.get("/portfolio/template")
def holdings_template():
    content = (
        ",".join(CSV_COLUMNS)
        + "\n600000.SH,浦发银行,stock,100,10.0000,2026-10-30,T1,示例行请修改或删除\n"
    )
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="positions-template.csv"'},
    )


@router.post("/portfolio/preview")
def preview_holdings(payload: CsvPreview):
    return preview_csv(payload.content)


@router.post("/portfolio/import")
def import_holdings(payload: PositionImport, request: Request, session: SessionDep):
    return import_lots(session, payload.rows, request.app.state.settings.market_provider)


@router.post("/portfolio/{lot_id}/update")
def update_holding(lot_id: str, payload: PositionInput, request: Request, session: SessionDep):
    return update_lot(session, lot_id, payload, request.app.state.settings.market_provider)


@router.post("/portfolio/{lot_id}/delete")
def delete_holding(lot_id: str, request: Request, session: SessionDep):
    return delete_lot(session, lot_id, request.app.state.settings.market_provider)
