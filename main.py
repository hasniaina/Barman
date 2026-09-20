from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from database import Order, init_db, get_db, Item, SaleHistory

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation unique de la BDD au demarrage du serveur
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# --- Routes d'affichage ---

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request, db: Session = Depends(get_db)):
    items = db.query(Item).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"items": items}
    )

# @app.get("/caisse")
# def gotoCaisse(request: Request):
#     return templates.TemplateResponse(request=request, name='caisse.html')

# --- VUE CAISSE ---

@app.get("/caisse", response_class=HTMLResponse)
async def caisse_view(request: Request, db: Session = Depends(get_db)):
    # Récupération des tables ayant au moins une commande active
    active_tables_query = db.query(Order.table_number).distinct().all()
    active_tables = {row[0] for row in active_tables_query}
    
    # Génération de 12 tables de démonstration
    tables = [
        {"number": i, "is_occupied": i in active_tables}
        for i in range(1, 13)
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="caisse.html",
        context={"tables": tables}
    )

# --- MODALE CONTENU TABLE ---

def render_table_card(table_number: int, is_occupied: bool, *, swap_oob: bool = False) -> str:
    border_class = "border-error" if is_occupied else "border-transparent"
    badge_class = "bg-error/20 text-error" if is_occupied else "bg-success/20 text-success"
    state_class = "is-occupied" if is_occupied else "is-free"
    oob_attr = ' hx-swap-oob="true"' if swap_oob else ""
    return f"""
    <div id="card-table-{table_number}"
         class="table-card card bg-base-100 shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 cursor-pointer border-2 {border_class} {state_class}"
         hx-get="/caisse/table/{table_number}"
         hx-target="#modal-container"
         hx-swap="innerHTML"
         hx-trigger="click"
         onclick="table_modal.showModal()"{oob_attr}>
        <div class="card-body items-center text-center p-6">
            <div class="w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold mb-2 {badge_class}">
                T-{table_number}
            </div>
            <h2 class="card-title text-base">Table {table_number}</h2>
        </div>
    </div>
    """


@app.get("/caisse/table/{table_number}", response_class=HTMLResponse)
async def get_table_details(table_number: int, request: Request, db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.table_number == table_number).all()
    items = db.query(Item).all()
    total = sum(order.quantity * order.price_at_sale for order in orders)

    return templates.TemplateResponse(
        request=request,
        name="table_modal_content.html",
        context={
            "table_number": table_number,
            "orders": orders,
            "items": items,
            "total": total
        }
    )


@app.post("/caisse/table/{table_number}/add", response_class=HTMLResponse)
async def add_to_order(
    table_number: int,
    request: Request,
    item_id: int = Form(...),
    quantity: int = Form(1),
    db: Session = Depends(get_db)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    # if not item or item.quantity < quantity:
    #     raise HTTPException(status_code=400, detail="Stock insuffisant")
    if not item.snack:
        item.quantity -= quantity

    new_order = Order(
        table_number=table_number,
        item_id=item_id,
        quantity=quantity,
        price_at_sale=item.price
    )
    db.add(new_order)
    db.commit()

    modal_response = await get_table_details(table_number, request, db)
    modal_html = modal_response.body.decode("utf-8")
    table_card_html = render_table_card(table_number, is_occupied=True, swap_oob=True)

    return HTMLResponse(content=modal_html + table_card_html)

@app.post("/caisse/table/{table_number}/checkout", response_class=HTMLResponse)
async def checkout_table(table_number: int, request: Request, db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.table_number == table_number).all()
    
    # Transfert des commandes vers l'historique des ventes
    for order in orders:
        history_entry = SaleHistory(
            table_number=order.table_number,
            item_name=order.item.name if order.item else "Article supprimé",
            quantity=order.quantity,
            price_at_sale=order.price_at_sale,
            total_price=order.quantity * order.price_at_sale,
            created_at=order.created_at
        )
        db.add(history_entry)
        db.delete(order)
    
    db.commit()

    return HTMLResponse(content=render_table_card(table_number, is_occupied=False))


@app.get("/historique", response_class=HTMLResponse)
async def get_history(request: Request, db: Session = Depends(get_db)):
    sales = db.query(SaleHistory).order_by(SaleHistory.created_at.desc()).all()
    total_recette = sum(sale.total_price for sale in sales)
    
    return templates.TemplateResponse(
        request=request,
        name="historique.html",
        context={
            "sales": sales,
            "total_recette": total_recette
        }
    )


@app.get("/caisse/table/{table_number}/card", response_class=HTMLResponse)
async def get_table_card(table_number: int, request: Request, db: Session = Depends(get_db)):
    is_occupied = db.query(Order).filter(Order.table_number == table_number).first() is not None
    return HTMLResponse(content=render_table_card(table_number, is_occupied))


def get_card_html(table_number: int, is_occupied: bool) -> str:
    return render_table_card(table_number, is_occupied)


@app.post("/items", response_class=HTMLResponse)
async def create_item(
    request: Request,
    name: str = Form(...),
    quantity: int = Form(...),
    price: str = Form(...),
    snack: bool = Form(False),
    db: Session = Depends(get_db)
):
    numeric_price = normalize_price(price)
    new_item = Item(name=name, quantity=quantity, price=numeric_price, snack=snack)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return templates.TemplateResponse(
        request=request,
        name="item_row.html",
        context={"item": new_item}
    )


@app.post("/items/{item_id}/adjust", response_class=HTMLResponse)
async def adjust_quantity(
    item_id: int,
    request: Request,
    delta: int = Form(...),
    db: Session = Depends(get_db)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")

    item.quantity = max(0, item.quantity + delta)
    db.commit()
    db.refresh(item)

    return templates.TemplateResponse(
        request=request,
        name="item_row.html",
        context={"item": item}
    )


@app.delete("/items/{item_id}", response_class=Response)
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")

    db.delete(item)
    db.commit()

    return Response(status_code=200)


@app.get("/items/search", response_class=HTMLResponse)
async def search_items(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db)
):
    query = db.query(Item)
    if q.strip():
        query = query.filter(Item.name.ilike(f"%{q.strip()}%"))

    items = query.all()

    return templates.TemplateResponse(
        request=request,
        name="item_rows.html",
        context={"items": items}
    )

# 1. Récupère le formulaire d'édition rempli avec les données de l'article
@app.get("/items/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_form(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trouvé")
    
    return templates.TemplateResponse(
        request=request,
        name="partials/edit_item_form.html",
        context={"item": item}
    )

# 2. Sauvegarde les modifications et renvoie la ligne <tr> mise à jour
@app.put("/items/{item_id}", response_class=HTMLResponse)
async def update_item(
    item_id: int,
    request: Request,
    name: str = Form(...),
    price: str = Form(...),
    quantity: int = Form(...),
    snack: bool = Form(False),
    db: Session = Depends(get_db)
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trouvé")

    item.name = name
    item.price = normalize_price(price)
    item.quantity = quantity
    item.snack = snack
    db.commit()
    db.refresh(item)

    return templates.TemplateResponse(
        request=request,
        name="item_row.html",
        context={"item": item}
    )


@app.api_route("/caisse/table/{table_number}/order/{order_id}/quantity", methods=["POST", "PUT"], response_class=HTMLResponse)
async def update_order_quantity(
    table_number: int,
    order_id: int,
    request: Request,
    quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.table_number == table_number).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    if quantity < 1:
        raise HTTPException(status_code=400, detail="La quantité doit être supérieure à 0")

    item = db.query(Item).filter(Item.id == order.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Article introuvable")

    delta = quantity - order.quantity
    if delta > 0 and item.quantity < delta:
        raise HTTPException(status_code=400, detail="Stock insuffisant pour cette modification")

    item.quantity -= delta
    order.quantity = quantity
    db.commit()

    return await get_table_details(table_number, request, db)

@app.delete("/caisse/table/{table_number}/order/{order_id}", response_class=HTMLResponse)
async def delete_order_from_table(
    table_number: int,
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.table_number == table_number).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    item = db.query(Item).filter(Item.id == order.item_id).first()
    if item and not item.snack:
        item.quantity += order.quantity

    db.delete(order)
    db.commit()

    modal_response = await get_table_details(table_number, request, db)
    modal_html = modal_response.body.decode("utf-8")
    remaining_orders = db.query(Order).filter(Order.table_number == table_number).count()
    table_card_html = render_table_card(table_number, is_occupied=remaining_orders > 0, swap_oob=True)

    return HTMLResponse(content=modal_html + table_card_html)

def normalize_price(value: str | float | int) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    text = text.replace("\u202F", "").replace("\u00A0", "").replace(" ", "")

    if not text or text == ".":
        return 0.0

    decimal_separator = ","

    if "," in text and "." in text:
        comma_pos = text.rfind(",")
        dot_pos = text.rfind(".")
        if comma_pos > dot_pos:
            text = text.replace(".", "").replace(",", ".")
            decimal_separator = ","
        else:
            text = text.replace(",", "")
            decimal_separator = "."
    elif "," in text:
        last_comma = text.rfind(",")
        if len(text) - last_comma <= 3:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        last_dot = text.rfind(".")
        if len(text) - last_dot > 3:
            text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return 0.0