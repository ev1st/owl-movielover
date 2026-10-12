import token
from urllib import request

from sqlalchemy import select
from fastapi import FastAPI, HTTPException, Response, Depends, Request
from starlette import status
from starlette.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from models import Item, UserLogin
from db import Session, ItemsORM, User
from authx import AuthX, AuthXConfig
import uvicorn
# from rich_spinner import show_skeleton_spinner



app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


config = AuthXConfig()
config.JWT_SECRET_KEY = "a_gde_maxim"
config.JWT_ACCESS_COOKIE_NAME = "access_token"
config.JWT_TOKEN_LOCATION = ["cookies"]
secretik = AuthX(config=config)



#
# config = AuthXConfig()
# config.JWT_SECRET_KEY = "www"
# config.JWT_ACCESS_COOKIE_NAME = "access_token"
# config.JWT_TOKEN_LOCATION = ["cookies"]
# security = AuthX(config)
#

@app.get("/", tags=["abdullik"])
def read_index(request: Request):
    return templates.TemplateResponse({"request": request}, "index.html", )


@app.post("/items", tags=["items"])
def create_item(item: Item):
    with Session() as session:
        item_orm = ItemsORM(
            creator=item.creator,
            model=item.model,
            price=item.price,
            category=item.category,
        )
        session.add(item_orm)
        session.commit()
        return "W"


@app.get("/items", tags=["items"])
def get_items():
    with Session() as session:
        result = session.execute(select(ItemsORM))
        data = result.scalars().all()
        session.commit()
        return "WWW.abdullik.com", data


@app.get("/items/{id_item}", tags=["items"])
def get_item(id_item: int):
    with Session() as session:
        result = session.execute(select(ItemsORM).where(ItemsORM.id == id_item))
        data = result.scalars().all()
        session.commit()
        print(data[0].id)
    return "WWW.abdullik.com", data


@app.get("/catalog", tags=["catalog"])
def get_catalog(request: Request):
    with Session() as session:
        result = session.execute(select(ItemsORM))
        data = result.scalars().all()
        session.commit()
        return templates.TemplateResponse(
            "catalog.html", {"request": request, "data": data}
        )



@app.post("/login", tags=["login"])
def redistracia(user_qwe: UserLogin, responce: Response):
    with Session() as session:
        stmt = select(User).where(User.username == user_qwe.username)
        data = session.scalars(stmt).first()
        if data and data.password == user_qwe.password:
            token = secretik.create_access_token(uid=str(data.id))
            responce.set_cookie(config.JWT_ACCESS_COOKIE_NAME, token)
            return {"access": token}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")



@app.get("/www", dependencies=[Depends(secretik.access_token_required)])
def get_www():
    return "www"







# @app.post("/login", tags=["login"])
# def login_post(creds: UserLogin, response: Response):
#     with Session() as session:
#         stmt = select(User).where(User.username == creds.username)
#         user = session.scalars(stmt).first()
#         if user and user.password == creds.password:
#             token = security.create_access_token(uid=str(user.id))
#             response.set_cookie(config.JWT_ACCESS_COOKIE_NAME, token)
#             return {"access_token": token, "token_type": "bearer"}
#         raise HTTPException(status_code=401, detail="Incorrect username or password")



# @app.post("/login")
# def login_user(user: UserLogin, response: Response):
#     if user:
#         with Session() as session:
#             data = session.scalars((select(User).where(User.username == user.username))).first()
#             if data:
#                 if data.password == user.password:
#                     token = security.create_access_token(uid=str(data.id))
#                     response.set_cookie(config.JWT_ACCESS_COOKIE_NAME, token)
#                     return {"access_token": token, "token_type": "bearer", "success": "победа"}
#             else:
#                 return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="не победа")
#     raise HTTPException(status_code=401, detail="Incorrect username or password")
#











if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    # show_skeleton_spinner(host="127.0.0.1", port=8000)
