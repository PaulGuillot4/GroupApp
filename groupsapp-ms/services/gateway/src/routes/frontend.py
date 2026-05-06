import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["frontend"])

# __file__ = .../services/gateway/src/routes/frontend.py
# three dirname calls reach .../services/gateway/
_gateway_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
templates = Jinja2Templates(directory=os.path.join(_gateway_root, "templates"))


@router.get("/")
def root():
    return RedirectResponse(url="/auth/login/", status_code=307)


@router.get("/auth/login/")
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html")


@router.get("/auth/register/")
def register_page(request: Request):
    return templates.TemplateResponse(request, "auth/register.html")


@router.get("/app/")
def chat_page(request: Request):
    return templates.TemplateResponse(request, "app/chat.html")
