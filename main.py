import re
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from datetime import date as DateType
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from database import SessionLocal, engine
from models import Base, User, FinanceRecord, RecordType
from auth import hash_password, verify_password
from categories import INCOME_CATEGORIES, EXPENSE_CATEGORIES


Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="secret123")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_valid_full_name(full_name: str) -> bool:
    # Перевірка: 3 слова, кожне з великої літери, дозволені літери українські або латиниця
    pattern = r"^([А-ЯҐЄІЇA-Z][а-яґєіїa-z]+)\s([А-ЯҐЄІЇA-Z][а-яґєіїa-z]+)\s([А-ЯҐЄІЇA-Z][а-яґєіїa-z]+)$"
    return re.match(pattern, full_name) is not None


def is_strong_password(password: str) -> bool:
    # Дозволені символи: латиниця, кирилиця, цифри, спецсимволи
    allowed_pattern = r"^[a-zA-Zа-яА-ЯіїєІЇЄґҐ0-9@#$%^&+=!_.,:;*(){}\[\]<>?-]+$"

    if len(password) < 8:
        return False

    if not re.fullmatch(allowed_pattern, password):
        return False

    # Принаймні одна літера (латиниця або кирилиця)
    if not re.search(r"[a-zA-Zа-яА-ЯіїєІЇЄґҐ]", password):
        return False

    # Принаймні одна цифра
    if not re.search(r"\d", password):
        return False

    # Принаймні один спецсимвол
    if not re.search(r"[@#$%^&+=!_.,:;*(){}\[\]<>?-]", password):
        return False

    return True



@app.get("/", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_post(request: Request,
          full_name: str = Form(...),
          password: str = Form(...),
          db: Session = Depends(get_db)):

    user = db.query(User).filter(User.full_name == full_name).first()
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Користувача не знайдено. Зареєструйтесь спочатку.",
            "full_name": full_name
        })

    if not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Невірний пароль.",
            "full_name": full_name
        })

    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)

    records = db.query(FinanceRecord).filter(FinanceRecord.user_id == user_id).all()

    # Мінімальна дата
    min_date_obj = db.query(func.min(FinanceRecord.date)).filter(FinanceRecord.user_id == user_id).scalar()
    min_date_str = min_date_obj.isoformat() if min_date_obj else None

    # Групуємо рейтинги і суми по категоріях окремо для доходів і витрат
    income_ratings = {}
    income_amounts = {}

    expense_ratings = {}
    expense_amounts = {}

    for r in records:
        if r.type == RecordType.income:
            # рейтинг
            if r.rating is not None:
                income_ratings.setdefault(r.category, []).append(r.rating)
            # сума
            income_amounts.setdefault(r.category, []).append(r.amount)
        elif r.type == RecordType.expense:
            # рейтинг
            if r.rating is not None:
                expense_ratings.setdefault(r.category, []).append(r.rating)
            # сума
            expense_amounts.setdefault(r.category, []).append(r.amount)

    # Обчислюємо середні рейтинги
    income_avg_result = {k: round(sum(v)/len(v), 2) for k, v in income_ratings.items()}
    expense_avg_result = {k: round(sum(v)/len(v), 2) for k, v in expense_ratings.items()}

    # Обчислюємо середні суми
    income_avg_amount_result = {k: round(sum(v)/len(v), 2) for k, v in income_amounts.items()}
    expense_avg_amount_result = {k: round(sum(v)/len(v), 2) for k, v in expense_amounts.items()}

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "records": records,
        "min_date": min_date_str,
        "income_avg_labels": list(income_avg_result.keys()),
        "income_avg_rating_values": list(income_avg_result.values()),
        "income_avg_amount_values": [income_avg_amount_result.get(cat, 0) for cat in income_avg_result.keys()],
        "expense_avg_labels": list(expense_avg_result.keys()),
        "expense_avg_rating_values": list(expense_avg_result.values()),
        "expense_avg_amount_values": [expense_avg_amount_result.get(cat, 0) for cat in expense_avg_result.keys()]
    })


@app.get("/add/income")
def add_income_form(request: Request):
    return templates.TemplateResponse("add_income.html", {
        "request": request,
        "income_categories": INCOME_CATEGORIES
    })

@app.get("/add/expense")
def add_expense_form(request: Request):
    return templates.TemplateResponse("add_expense.html", {
        "request": request,
        "expense_categories": EXPENSE_CATEGORIES
    })


@app.post("/add/income")
def add_income(
    request: Request,
    date_str: str = Form(...),
    category: str = Form(...),
    name: str | None = Form(None),
    amount: float = Form(...),
    rating: int = Form(...),
    is_monthly: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)

    if category not in INCOME_CATEGORIES:
        raise HTTPException(status_code=400, detail="Невідома категорія доходу")

    if name and len(name) > 100:
        raise HTTPException(status_code=400, detail="Назва занадто довга")

    monthly_flag = is_monthly == "on"
    date_obj = DateType.fromisoformat(date_str)

    # Якщо щомісячний, перевірка що дата не в майбутньому
    if monthly_flag and date_obj > date.today():
        raise HTTPException(status_code=400, detail="Дата початку щомісячного доходу не може бути в майбутньому")

    record = FinanceRecord(
        user_id=user_id,
        date=date_obj,
        category=category,
        name=name,
        amount=amount,
        rating=rating,
        is_monthly=monthly_flag,
        type=RecordType.income
    )
    db.add(record)
    db.commit()

    return RedirectResponse("/dashboard", status_code=302)


@app.post("/add/expense")
def add_expense(
    request: Request,
    date_str: str = Form(...),
    category: str = Form(...),
    name: str | None = Form(None),
    amount: float = Form(...),
    rating: int = Form(...),
    is_monthly: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)

    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Невідома категорія витрат")

    if name and len(name) > 100:
        raise HTTPException(status_code=400, detail="Назва занадто довга")

    monthly_flag = is_monthly == "on"
    date_obj = DateType.fromisoformat(date_str)

    if monthly_flag and date_obj > date.today():
        raise HTTPException(status_code=400, detail="Дата початку щомісячної витрати не може бути в майбутньому")

    record = FinanceRecord(
        user_id=user_id,
        date=date_obj,
        category=category,
        name=name,
        amount=amount,
        rating=rating,
        is_monthly=monthly_flag,
        type=RecordType.expense
    )
    db.add(record)
    db.commit()

    return RedirectResponse("/dashboard", status_code=302)


@app.get("/register", response_class=HTMLResponse)
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_post(request: Request,
                  full_name: str = Form(...),
                  password: str = Form(...),
                  db: Session = Depends(get_db)):

    if not is_valid_full_name(full_name):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Введіть ПІБ у форматі: Прізвище Ім'я По-батькові, всі з великої літери.",
            "full_name": full_name,
            "password": password
        })

    if not is_strong_password(password):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": ("Пароль має містити мінімум 8 символів, принаймні одну літеру (латиниця або кирилиця), "
                      "одну цифру та один спеціальний символ (@#$%^&+=!_.,:;*(){}[]<>?-), без пробілів."),
            "full_name": full_name
        })

    if len(full_name) > 100:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "ПІБ занадто довге (максимум 100 символів).",
            "full_name": full_name,
            "password": password
        })

    existing_user = db.query(User).filter(User.full_name == full_name).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Користувач із таким ПІБ вже існує.",
            "full_name": full_name,
            "password": password
        })

    new_user = User(
        full_name=full_name,
        password_hash=hash_password(password)
    )
    db.add(new_user)
    db.commit()
    request.session["user_id"] = new_user.id
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/delete/{record_id}")
def delete_record(record_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)

    record = db.query(FinanceRecord).filter(FinanceRecord.id == record_id, FinanceRecord.user_id == user_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Запис не знайдено")

    db.delete(record)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)
