"""Products, categories, suppliers and customers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from deps import Context, require_permission
from errors import ConflictError, NotFoundError, ValidationError
from models import (
    Product,
    ProductCategory,
    ProductStatus,
    ProductType,
    Supplier,
    Customer,
    utcnow,
)
from routers.common import clean, get_or_404, paginated
from services.audit import record_audit

router = APIRouter(tags=["catalog"])


class ProductPayload(BaseModel):
    sku: str
    name: str
    barcode: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    brand: Optional[str] = None
    product_type: ProductType = ProductType.FINISHED_GOOD
    status: ProductStatus = ProductStatus.ACTIVE
    base_unit: str = "PCS"
    cost_price: float = 0.0
    selling_price: Optional[float] = None
    reorder_point: float = 0.0
    reorder_quantity: float = 0.0
    track_batch: bool = False
    track_expiry: bool = False
    track_serial: bool = False
    shelf_life_days: Optional[int] = None
    weight_kg: Optional[float] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    image_url: Optional[str] = None


class CategoryPayload(BaseModel):
    name: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    description: Optional[str] = None


class SupplierPayload(BaseModel):
    code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    tax_number: Optional[str] = None
    payment_terms: Optional[str] = None


class CustomerPayload(BaseModel):
    code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    tax_number: Optional[str] = None
    credit_limit: float = 0.0


# ---------------------------------------------------------------- products

@router.get("/products")
async def list_products(ctx: Context = Depends(require_permission("product:read")),
                        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                        search: Optional[str] = None,
                        category_id: Optional[str] = None,
                        status: Optional[ProductStatus] = None,
                        include_archived: bool = False) -> Dict[str, Any]:
    query = ctx.scope()
    if not include_archived:
        query["is_archived"] = False
    if category_id:
        query["category_id"] = category_id
    if status:
        query["status"] = status.value
    if search:
        query["$or"] = [
            {"sku": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
            {"barcode": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "products", query, page=page, page_size=page_size,
                           sort=[("sku", 1)])


@router.get("/products/lookup")
async def lookup_product(code: str = Query(...),
                         ctx: Context = Depends(require_permission("product:read"))) -> Dict[str, Any]:
    """Resolve a scanned barcode or SKU to a product."""
    tenant_id = ctx.require_tenant()
    query = {"tenant_id": tenant_id,
             "$or": [{"barcode": code}, {"sku": code.upper()}, {"sku": code}]}
    product = await ctx.store.find_one("products", query)
    if not product:
        raise NotFoundError("No product matches that code")
    return product


@router.post("/products", status_code=201)
async def create_product(payload: ProductPayload,
                         ctx: Context = Depends(require_permission("product:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if await ctx.store.find_one("products", {"tenant_id": tenant_id, "sku": payload.sku.upper()}):
        raise ConflictError("A product with this SKU already exists")
    if payload.barcode and await ctx.store.find_one("products",
                                                    {"tenant_id": tenant_id, "barcode": payload.barcode}):
        raise ConflictError("A product with this barcode already exists")
    product = Product(tenant_id=tenant_id, **payload.model_dump())
    product.sku = product.sku.upper()
    doc = product.model_dump(mode="python")
    await ctx.store.insert_one("products", doc)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="create",
                       entity_type="product", entity_id=doc["id"], after=doc, **ctx.client_meta())
    return doc


@router.get("/products/{product_id}")
async def get_product(product_id: str,
                      ctx: Context = Depends(require_permission("product:read"))) -> Dict[str, Any]:
    return await get_or_404(ctx.store, "products", ctx, product_id)


@router.patch("/products/{product_id}")
async def update_product(product_id: str, payload: ProductPayload,
                         ctx: Context = Depends(require_permission("product:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "products", ctx, product_id)
    updates = clean(payload.model_dump())
    updates = {k: (v.value if hasattr(v, "value") else v) for k, v in updates.items()}
    if "sku" in updates:
        updates["sku"] = updates["sku"].upper()
        clash = await ctx.store.find_one("products",
                                         {"tenant_id": tenant_id, "sku": updates["sku"]})
        if clash and clash["id"] != product_id:
            raise ConflictError("A product with this SKU already exists")
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("products", {"id": product_id, "tenant_id": tenant_id},
                               set_fields=updates)
    await record_audit(ctx.store, tenant_id=tenant_id, user=ctx.user, action="update",
                       entity_type="product", entity_id=product_id, after=updates,
                       **ctx.client_meta())
    return await ctx.store.find_one("products", {"id": product_id})


@router.delete("/products/{product_id}", status_code=204)
async def archive_product(product_id: str,
                          ctx: Context = Depends(require_permission("product:delete"))) -> None:
    tenant_id = ctx.require_tenant()
    await get_or_404(ctx.store, "products", ctx, product_id)
    await ctx.store.update_one("products", {"id": product_id, "tenant_id": tenant_id},
                               set_fields={"is_archived": True,
                                           "status": ProductStatus.INACTIVE.value,
                                           "updated_at": utcnow()})


# ---------------------------------------------------------------- categories

@router.get("/categories")
async def list_categories(ctx: Context = Depends(require_permission("product:read"))) -> Dict[str, Any]:
    items = await ctx.store.find_many("product_categories", ctx.scope(), sort=[("name", 1)])
    return {"items": items}


@router.post("/categories", status_code=201)
async def create_category(payload: CategoryPayload,
                          ctx: Context = Depends(require_permission("product:write"))) -> Dict[str, Any]:
    category = ProductCategory(tenant_id=ctx.require_tenant(), **payload.model_dump())
    doc = category.model_dump(mode="python")
    await ctx.store.insert_one("product_categories", doc)
    return doc


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(category_id: str,
                          ctx: Context = Depends(require_permission("product:write"))) -> None:
    await get_or_404(ctx.store, "product_categories", ctx, category_id)
    await ctx.store.delete_one("product_categories", ctx.scope({"id": category_id}))


# ---------------------------------------------------------------- suppliers

@router.get("/suppliers")
async def list_suppliers(ctx: Context = Depends(require_permission("product:read")),
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                         search: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"code": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "suppliers", query, page=page, page_size=page_size,
                           sort=[("name", 1)])


@router.post("/suppliers", status_code=201)
async def create_supplier(payload: SupplierPayload,
                          ctx: Context = Depends(require_permission("product:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if await ctx.store.find_one("suppliers", {"tenant_id": tenant_id, "code": payload.code.upper()}):
        raise ConflictError("A supplier with this code already exists")
    supplier = Supplier(tenant_id=tenant_id, **payload.model_dump())
    supplier.code = supplier.code.upper()
    doc = supplier.model_dump(mode="python")
    await ctx.store.insert_one("suppliers", doc)
    return doc


@router.patch("/suppliers/{supplier_id}")
async def update_supplier(supplier_id: str, payload: SupplierPayload,
                          ctx: Context = Depends(require_permission("product:write"))) -> Dict[str, Any]:
    await get_or_404(ctx.store, "suppliers", ctx, supplier_id)
    updates = clean(payload.model_dump())
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("suppliers", ctx.scope({"id": supplier_id}), set_fields=updates)
    return await ctx.store.find_one("suppliers", ctx.scope({"id": supplier_id}))


# ---------------------------------------------------------------- customers

@router.get("/customers")
async def list_customers(ctx: Context = Depends(require_permission("outbound:read")),
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                         search: Optional[str] = None) -> Dict[str, Any]:
    query = ctx.scope()
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"code": {"$regex": search, "$options": "i"}},
        ]
    return await paginated(ctx.store, "customers", query, page=page, page_size=page_size,
                           sort=[("name", 1)])


@router.post("/customers", status_code=201)
async def create_customer(payload: CustomerPayload,
                          ctx: Context = Depends(require_permission("outbound:write"))) -> Dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if await ctx.store.find_one("customers", {"tenant_id": tenant_id, "code": payload.code.upper()}):
        raise ConflictError("A customer with this code already exists")
    customer = Customer(tenant_id=tenant_id, **payload.model_dump())
    customer.code = customer.code.upper()
    doc = customer.model_dump(mode="python")
    await ctx.store.insert_one("customers", doc)
    return doc


@router.patch("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: CustomerPayload,
                          ctx: Context = Depends(require_permission("outbound:write"))) -> Dict[str, Any]:
    await get_or_404(ctx.store, "customers", ctx, customer_id)
    updates = clean(payload.model_dump())
    updates["updated_at"] = utcnow()
    await ctx.store.update_one("customers", ctx.scope({"id": customer_id}), set_fields=updates)
    return await ctx.store.find_one("customers", ctx.scope({"id": customer_id}))
