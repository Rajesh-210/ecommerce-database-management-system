import os, time
from decimal import Decimal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pymysql
from pymysql.cursors import DictCursor

DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT","3306")),
          user=os.getenv("DB_USER","edms_user"), password=os.getenv("DB_PASSWORD",""),
          database=os.getenv("DB_NAME","ecommerce_db"), cursorclass=DictCursor,
          autocommit=False, connect_timeout=5)

app = FastAPI(title="EDMS API", version="1.0.0")
origins = os.getenv("CORS_ORIGINS","*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

def connect():
    last = None
    for _ in range(20):
        try:
            return pymysql.connect(**DB)
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise HTTPException(status_code=503, detail=f"Database unavailable: {last}")

class CustomerIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str | None = None
    country: str | None = None

class ProductIn(BaseModel):
    category_id: int | None = None
    product_name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    sku: str
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class OrderIn(BaseModel):
    customer_id: int
    items: list[OrderItemIn] = Field(min_length=1)
    payment_method: str = "UPI"

@app.get("/health")
def health():
    conn = connect()
    try:
        with conn.cursor() as cur: cur.execute("SELECT 1")
        return {"status":"ok","database":"connected"}
    finally: conn.close()

@app.get("/api/dashboard")
def dashboard():
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) n FROM customers"); customers=c.fetchone()["n"]
            c.execute("SELECT COUNT(*) n FROM products"); products=c.fetchone()["n"]
            c.execute("SELECT COUNT(*) n FROM orders"); orders=c.fetchone()["n"]
            c.execute("SELECT COALESCE(SUM(total_amount),0) total FROM orders WHERE order_status <> 'CANCELLED'")
            sales=c.fetchone()["total"]
            c.execute("""SELECT DATE_FORMAT(created_at,'%Y-%m') month,
                         SUM(total_amount) sales FROM orders
                         WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                         GROUP BY DATE_FORMAT(created_at,'%Y-%m') ORDER BY month""")
            trend=c.fetchall()
        return {"customers":customers,"products":products,"orders":orders,
                "sales":float(sales),"sales_trend":[{"month":r["month"],"sales":float(r["sales"])} for r in trend]}
    finally: conn.close()

@app.get("/api/customers")
def customers():
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM customers ORDER BY customer_id DESC")
            return c.fetchall()
    finally: conn.close()

@app.post("/api/customers", status_code=201)
def add_customer(item: CustomerIn):
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO customers(full_name,email,phone,country) VALUES(%s,%s,%s,%s)",
                      (item.full_name,item.email,item.phone,item.country))
            conn.commit()
            return {"customer_id":c.lastrowid,"message":"Customer created"}
    except pymysql.err.IntegrityError as e:
        conn.rollback(); raise HTTPException(409, "Email already exists")
    finally: conn.close()

@app.get("/api/products")
def products():
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("""SELECT p.*, c.category_name FROM products p
                         LEFT JOIN categories c ON p.category_id=c.category_id
                         ORDER BY p.product_id DESC""")
            rows=c.fetchall()
            for r in rows: r["price"]=float(r["price"])
            return rows
    finally: conn.close()

@app.post("/api/products", status_code=201)
def add_product(item: ProductIn):
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("""INSERT INTO products(category_id,product_name,description,sku,price,stock_quantity)
                         VALUES(%s,%s,%s,%s,%s,%s)""",
                      (item.category_id,item.product_name,item.description,item.sku,item.price,item.stock_quantity))
            conn.commit()
            return {"product_id":c.lastrowid,"message":"Product created"}
    except pymysql.err.IntegrityError:
        conn.rollback(); raise HTTPException(409,"SKU already exists or category is invalid")
    finally: conn.close()

@app.put("/api/products/{product_id}")
def update_product(product_id: int, item: ProductIn):
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("""UPDATE products SET category_id=%s,product_name=%s,description=%s,
                         sku=%s,price=%s,stock_quantity=%s WHERE product_id=%s""",
                      (item.category_id,item.product_name,item.description,item.sku,item.price,item.stock_quantity,product_id))
            if c.rowcount == 0:
                c.execute("SELECT product_id FROM products WHERE product_id=%s",(product_id,))
                if not c.fetchone(): raise HTTPException(404,"Product not found")
            conn.commit()
            return {"message":"Product updated"}
    except:
        conn.rollback(); raise
    finally: conn.close()

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM products WHERE product_id=%s",(product_id,))
            if c.rowcount == 0: raise HTTPException(404,"Product not found")
            conn.commit()
            return {"message":"Product deleted"}
    except pymysql.err.IntegrityError:
        conn.rollback(); raise HTTPException(409,"Product is referenced by an order and cannot be deleted")
    finally: conn.close()

@app.get("/api/orders")
def orders():
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("""SELECT o.order_id,o.order_status,o.total_amount,o.created_at,
                         cu.full_name customer_name,cu.email
                         FROM orders o JOIN customers cu ON cu.customer_id=o.customer_id
                         ORDER BY o.order_id DESC""")
            rows=c.fetchall()
            for r in rows: r["total_amount"]=float(r["total_amount"])
            return rows
    finally: conn.close()

@app.post("/api/orders", status_code=201)
def create_order(item: OrderIn):
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("SELECT customer_id FROM customers WHERE customer_id=%s",(item.customer_id,))
            if not c.fetchone(): raise HTTPException(404,"Customer not found")
            total=Decimal("0.00"); lines=[]
            for line in item.items:
                c.execute("SELECT product_id,price,stock_quantity FROM products WHERE product_id=%s FOR UPDATE",(line.product_id,))
                p=c.fetchone()
                if not p: raise HTTPException(404,f"Product {line.product_id} not found")
                if p["stock_quantity"] < line.quantity: raise HTTPException(409,f"Insufficient stock for product {line.product_id}")
                total += p["price"] * line.quantity
                lines.append((line.product_id,line.quantity,p["price"]))
            c.execute("INSERT INTO orders(customer_id,total_amount) VALUES(%s,%s)",(item.customer_id,total))
            order_id=c.lastrowid
            for pid,qty,price in lines:
                c.execute("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(%s,%s,%s,%s)",
                          (order_id,pid,qty,price))
                c.execute("UPDATE products SET stock_quantity=stock_quantity-%s WHERE product_id=%s",(qty,pid))
            c.execute("""INSERT INTO payments(order_id,amount,payment_method,payment_status,transaction_reference)
                         VALUES(%s,%s,%s,'SUCCESS',%s)""",(order_id,total,item.payment_method,f"DEMO-{order_id}"))
            c.execute("UPDATE orders SET order_status='CONFIRMED' WHERE order_id=%s",(order_id,))
            conn.commit()
            return {"order_id":order_id,"total_amount":float(total),"status":"CONFIRMED",
                    "note":"Demo payment record only; no real payment was processed."}
    except:
        conn.rollback(); raise
    finally: conn.close()

@app.get("/api/categories")
def categories():
    conn=connect()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM categories ORDER BY category_name")
            return c.fetchall()
    finally: conn.close()
