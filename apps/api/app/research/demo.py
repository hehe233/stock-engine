from app.providers.research import fetch_research
from app.research.collection import store_snapshot
from app.research.queries import latest_snapshot, query_key
from app.research.schemas import FetchRequest
from app.shared.time import SHANGHAI, utc_now


def bootstrap_demo(sessions, settings):
    today = utc_now().astimezone(SHANGHAI).date()
    for kind in ("ladder", "dragon", "flow", "notices"):
        query = FetchRequest(kind=kind, date=today)
        with sessions() as session:
            if not latest_snapshot(session, query_key(query, "demo")):
                store_snapshot(
                    session, query, "demo", fetch_research(query.model_dump(mode="json"), "demo", 5)
                )
                session.commit()
