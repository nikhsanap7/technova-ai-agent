from fastapi import FastAPI

from backend.routes import customers, orders, products, invoices

app = FastAPI(
    title="TechNova GmbH Enterprise API",
    description="Simulated enterprise software API (fictional data).",
    version="1.0.0",
)

app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(invoices.router)


@app.get("/", tags=["Health"])
def health():
    return {"service": "TechNova Enterprise API", "status": "running"}