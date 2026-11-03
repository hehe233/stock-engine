from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_session(request: Request):
    # 每个请求拥有独立 Session，请求结束自动关闭，不能跨请求共享 Session。
    with request.app.state.sessions() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
