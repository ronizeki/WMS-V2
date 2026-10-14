from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# ============================================================================
# ENUMS
# ============================================================================

class TenantStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIAL = "trial"
    EXPIRED = "expired"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BLOCKED = "blocked"


class WarehouseStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


class LocationType(str, Enum):
    RECEIVING = "receiving"
    STORAGE = "storage"
    PICKING = "picking"
    SHIPPING = "shipping"
    QUARANTINE = "quarantine"
    RETURNS = "returns"
    DAMAGES = "damages"
    RESERVED = "reserved"


class LocationStatus(str, Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    BLOCKED = "blocked"
    MAINTENANCE = "maintenance"


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"
    DRAFT = "draft"


class ProductType(str, Enum):
    FINISHED_GOOD = "finished_good"
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    CONSUMABLE = "consumable"
    SPARE_PART = "spare_part"


class InventoryStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    DAMAGED = "damaged"
    QUARANTINE = "quarantine"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


class StockMovementType(str, Enum):
    INBOUND_RECEIPT = "inbound_receipt"
    OUTBOUND_SHIPMENT = "outbound_shipment"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    PUTAWAY = "putaway"
    PICKING = "picking"
    RETURN_IN = "return_in"
    RETURN_OUT = "return_out"
    CYCLE_COUNT_ADJUSTMENT = "cycle_count_adjustment"
    DAMAGED = "damaged"
    QUARANTINE = "quarantine"
    UNQUARANTINE = "unquarantine"
    EXPIRED = "expired"
    REVERSAL = "reversal"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class GoodsReceiptStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PutawayStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SalesOrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ALLOCATED = "allocated"
    PICKING = "picking"
    PICKED = "picked"
    PACKING = "packing"
    PACKED = "packed"
    PARTIALLY_SHIPPED = "partially_shipped"
    SHIPPED = "shipped"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ShipmentStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    PARTIALLY_DELIVERED = "partially_delivered"
    CANCELLED = "cancelled"


class TransferStatus(str, Enum):
    DRAFT = "draft"
    REQUESTED = "requested"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    PARTIALLY_RECEIVED = "partially_received"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CycleCountStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AdjustmentReason(str, Enum):
    DAMAGE = "damage"
    LOSS = "loss"
    FOUND = "found"
    EXPIRY = "expiry"
    DATA_CORRECTION = "data_correction"
    QUALITY_CONTROL = "quality_control"
    RETURN = "return"
    OTHER = "other"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class RoleCode(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    TENANT_OWNER = "tenant_owner"
    TENANT_ADMIN = "tenant_admin"
    WAREHOUSE_MANAGER = "warehouse_manager"
    WAREHOUSE_SUPERVISOR = "warehouse_supervisor"
    WAREHOUSE_OPERATOR = "warehouse_operator"
    VIEWER = "viewer"


# ============================================================================
# TENANT / SUBSCRIPTION
# ============================================================================

class TenantSettings(BaseModel):
    allow_negative_stock: bool = False
    require_adjustment_approval: bool = False
    require_transfer_approval: bool = False
    require_cycle_count_approval: bool = True
    low_stock_notifications: bool = True
    auto_create_putaway_tasks: bool = True
    costing_method: str = "weighted_average"
    reservation_timeout_minutes: int = 30
    batch_tracking_default: bool = False
    serial_tracking_default: bool = False


class Tenant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    name: str
    code: str
    status: TenantStatus = TenantStatus.ACTIVE
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"
    locale: str = "id_ID"
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "Indonesia"
    logo_url: Optional[str] = None
    website: Optional[str] = None
    tax_number: Optional[str] = None
    is_demo: bool = False
    settings: TenantSettings = Field(default_factory=TenantSettings)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    name: str
    code: str
    price: float = 0.0
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    max_users: int = 10
    max_warehouses: int = 1
    max_products: int = 1000
    max_locations: int = 100
    storage_gb: int = 10
    api_calls_monthly: int = 10000
    features: List[str] = Field(default_factory=list)
    is_active: bool = True
    is_free: bool = False
    trial_days: int = 14
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Subscription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    plan_id: str
    status: SubscriptionStatus = SubscriptionStatus.TRIAL
    start_date: datetime = Field(default_factory=utcnow)
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    amount: float = 0.0
    currency: str = "IDR"
    auto_renew: bool = True
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# USER / ROLE / PERMISSION
# ============================================================================

class Permission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    code: str
    name: str
    category: str
    description: Optional[str] = None


# Canonical permission catalog - "<resource>:<action>"
PERMISSION_CATALOG: List[Dict[str, str]] = [
    {"code": "dashboard:read", "name": "View dashboard", "category": "dashboard"},
    {"code": "product:read", "name": "View products", "category": "products"},
    {"code": "product:write", "name": "Create/edit products", "category": "products"},
    {"code": "product:delete", "name": "Archive products", "category": "products"},
    {"code": "product:import", "name": "Import products", "category": "products"},
    {"code": "inventory:read", "name": "View inventory", "category": "inventory"},
    {"code": "inventory:adjust", "name": "Adjust stock", "category": "inventory"},
    {"code": "inventory:approve", "name": "Approve stock adjustments", "category": "inventory"},
    {"code": "warehouse:read", "name": "View warehouses", "category": "warehouses"},
    {"code": "warehouse:write", "name": "Manage warehouses/locations", "category": "warehouses"},
    {"code": "inbound:read", "name": "View receiving", "category": "inbound"},
    {"code": "inbound:write", "name": "Receive goods", "category": "inbound"},
    {"code": "inbound:approve", "name": "Approve receipts", "category": "inbound"},
    {"code": "outbound:read", "name": "View orders/shipments", "category": "outbound"},
    {"code": "outbound:write", "name": "Create/edit orders", "category": "outbound"},
    {"code": "outbound:pick", "name": "Pick orders", "category": "outbound"},
    {"code": "outbound:pack", "name": "Pack orders", "category": "outbound"},
    {"code": "outbound:ship", "name": "Post shipments", "category": "outbound"},
    {"code": "transfer:read", "name": "View transfers", "category": "transfers"},
    {"code": "transfer:write", "name": "Create/process transfers", "category": "transfers"},
    {"code": "transfer:approve", "name": "Approve transfers", "category": "transfers"},
    {"code": "stocktake:read", "name": "View cycle counts", "category": "stocktake"},
    {"code": "stocktake:write", "name": "Count stock", "category": "stocktake"},
    {"code": "stocktake:approve", "name": "Approve cycle counts", "category": "stocktake"},
    {"code": "report:read", "name": "View reports", "category": "reports"},
    {"code": "report:export", "name": "Export reports", "category": "reports"},
    {"code": "user:read", "name": "View users", "category": "users"},
    {"code": "user:write", "name": "Manage users", "category": "users"},
    {"code": "role:read", "name": "View roles", "category": "roles"},
    {"code": "role:write", "name": "Manage roles/permissions", "category": "roles"},
    {"code": "settings:read", "name": "View settings", "category": "settings"},
    {"code": "settings:write", "name": "Manage settings", "category": "settings"},
    {"code": "subscription:read", "name": "View subscription", "category": "subscriptions"},
    {"code": "subscription:write", "name": "Manage subscription", "category": "subscriptions"},
    {"code": "audit:read", "name": "View audit log", "category": "audit"},
    {"code": "tenant:manage", "name": "Manage tenants (platform)", "category": "tenants"},
    {"code": "plan:manage", "name": "Manage plans (platform)", "category": "subscriptions"},
]

ALL_PERMISSIONS = [p["code"] for p in PERMISSION_CATALOG]

# Default role -> permission matrix
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    RoleCode.PLATFORM_ADMIN.value: ALL_PERMISSIONS,
    RoleCode.TENANT_OWNER.value: [p for p in ALL_PERMISSIONS if p != "tenant:manage"],
    RoleCode.TENANT_ADMIN.value: [
        p for p in ALL_PERMISSIONS
        if p not in ("tenant:manage", "plan:manage")
    ],
    RoleCode.WAREHOUSE_MANAGER.value: [
        "dashboard:read", "product:read", "product:write", "product:import",
        "inventory:read", "inventory:adjust", "inventory:approve",
        "warehouse:read", "warehouse:write",
        "inbound:read", "inbound:write", "inbound:approve",
        "outbound:read", "outbound:write", "outbound:pick", "outbound:pack", "outbound:ship",
        "transfer:read", "transfer:write", "transfer:approve",
        "stocktake:read", "stocktake:write", "stocktake:approve",
        "report:read", "report:export",
        "user:read", "role:read", "settings:read", "subscription:read", "audit:read",
    ],
    RoleCode.WAREHOUSE_SUPERVISOR.value: [
        "dashboard:read", "product:read",
        "inventory:read", "inventory:adjust", "inventory:approve",
        "warehouse:read",
        "inbound:read", "inbound:write", "inbound:approve",
        "outbound:read", "outbound:write", "outbound:pick", "outbound:pack",
        "transfer:read", "transfer:write", "transfer:approve",
        "stocktake:read", "stocktake:write", "stocktake:approve",
        "report:read", "report:export", "user:read", "audit:read",
    ],
    RoleCode.WAREHOUSE_OPERATOR.value: [
        "dashboard:read", "product:read", "inventory:read",
        "warehouse:read", "inbound:read", "inbound:write",
        "outbound:read", "outbound:pick", "outbound:pack",
        "transfer:read", "transfer:write", "stocktake:read", "stocktake:write",
    ],
    RoleCode.VIEWER.value: [
        "dashboard:read", "product:read", "inventory:read", "warehouse:read",
        "inbound:read", "outbound:read", "transfer:read", "stocktake:read",
        "report:read",
    ],
}

DEFAULT_ROLE_NAMES: Dict[str, str] = {
    RoleCode.PLATFORM_ADMIN.value: "Platform Administrator",
    RoleCode.TENANT_OWNER.value: "Tenant Owner",
    RoleCode.TENANT_ADMIN.value: "Tenant Administrator",
    RoleCode.WAREHOUSE_MANAGER.value: "Warehouse Manager",
    RoleCode.WAREHOUSE_SUPERVISOR.value: "Warehouse Supervisor",
    RoleCode.WAREHOUSE_OPERATOR.value: "Warehouse Operator",
    RoleCode.VIEWER.value: "Viewer / Auditor",
}

TENANT_ROLE_CODES = [
    RoleCode.TENANT_OWNER.value,
    RoleCode.TENANT_ADMIN.value,
    RoleCode.WAREHOUSE_MANAGER.value,
    RoleCode.WAREHOUSE_SUPERVISOR.value,
    RoleCode.WAREHOUSE_OPERATOR.value,
    RoleCode.VIEWER.value,
]


class Role(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: Optional[str] = None  # None = platform/global role template
    code: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    is_system: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: Optional[str] = None  # None for platform admins
    email: str
    full_name: str
    hashed_password: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE
    role_ids: List[str] = Field(default_factory=list)
    role_codes: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    warehouse_ids: List[str] = Field(default_factory=list)
    is_platform_admin: bool = False
    last_login_at: Optional[datetime] = None
    invited_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# WAREHOUSE / LOCATION
# ============================================================================

class Warehouse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    code: str
    name: str
    status: WarehouseStatus = WarehouseStatus.ACTIVE
    timezone: str = "Asia/Jakarta"
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "Indonesia"
    phone: Optional[str] = None
    manager_id: Optional[str] = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class WarehouseZone(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    warehouse_id: str
    code: str
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class WarehouseLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    warehouse_id: str
    zone_id: Optional[str] = None
    code: str
    name: Optional[str] = None
    location_type: LocationType = LocationType.STORAGE
    status: LocationStatus = LocationStatus.AVAILABLE
    aisle: Optional[str] = None
    rack: Optional[str] = None
    shelf: Optional[str] = None
    bin: Optional[str] = None
    max_capacity: Optional[float] = None
    max_weight_kg: Optional[float] = None
    is_pickable: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# PRODUCT
# ============================================================================

class UnitOfMeasure(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: Optional[str] = None
    code: str
    name: str
    is_base: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class ProductUnitConversion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    product_id: str
    from_unit: str
    to_unit: str
    factor: float
    created_at: datetime = Field(default_factory=utcnow)


class ProductCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    name: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    sku: str
    barcode: Optional[str] = None
    name: str
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
    is_archived: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# SUPPLIER / CUSTOMER
# ============================================================================

class Supplier(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: str = "Indonesia"
    tax_number: Optional[str] = None
    payment_terms: Optional[str] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Customer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    code: str
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: str = "Indonesia"
    tax_number: Optional[str] = None
    credit_limit: float = 0.0
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# PURCHASE ORDER / GOODS RECEIPT
# ============================================================================

class PurchaseOrderLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    ordered_qty: float
    received_qty: float = 0.0
    unit: str = "PCS"
    unit_cost: float = 0.0
    notes: Optional[str] = None


class PurchaseOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    supplier_id: str
    supplier_name: Optional[str] = None
    warehouse_id: str
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    order_date: datetime = Field(default_factory=utcnow)
    expected_date: Optional[datetime] = None
    currency: str = "IDR"
    notes: Optional[str] = None
    lines: List[PurchaseOrderLine] = Field(default_factory=list)
    total_amount: float = 0.0
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class GoodsReceiptLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    po_line_id: Optional[str] = None
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    expected_qty: float = 0.0
    received_qty: float = 0.0
    damaged_qty: float = 0.0
    rejected_qty: float = 0.0
    unit: str = "PCS"
    unit_cost: float = 0.0
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    serial_numbers: List[str] = Field(default_factory=list)
    receiving_location_id: Optional[str] = None
    notes: Optional[str] = None
    putaway_qty: float = 0.0


class GoodsReceipt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    purchase_order_id: Optional[str] = None
    purchase_order_number: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    warehouse_id: str
    status: GoodsReceiptStatus = GoodsReceiptStatus.DRAFT
    receipt_date: datetime = Field(default_factory=utcnow)
    notes: Optional[str] = None
    lines: List[GoodsReceiptLine] = Field(default_factory=list)
    posted: bool = False
    posted_at: Optional[datetime] = None
    posted_by: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PutawayTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    goods_receipt_id: Optional[str] = None
    warehouse_id: str
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    quantity: float
    putaway_qty: float = 0.0
    from_location_id: Optional[str] = None
    to_location_id: Optional[str] = None
    status: PutawayStatus = PutawayStatus.PENDING
    assigned_to: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# SALES ORDER / SHIPMENT
# ============================================================================

class SalesOrderLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    ordered_qty: float
    reserved_qty: float = 0.0
    picked_qty: float = 0.0
    packed_qty: float = 0.0
    shipped_qty: float = 0.0
    unit: str = "PCS"
    unit_price: float = 0.0
    notes: Optional[str] = None
    allocations: List[Dict[str, Any]] = Field(default_factory=list)


class SalesOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    customer_id: str
    customer_name: Optional[str] = None
    warehouse_id: str
    status: SalesOrderStatus = SalesOrderStatus.DRAFT
    priority: TaskPriority = TaskPriority.MEDIUM
    order_date: datetime = Field(default_factory=utcnow)
    requested_ship_date: Optional[datetime] = None
    currency: str = "IDR"
    notes: Optional[str] = None
    reference: Optional[str] = None
    lines: List[SalesOrderLine] = Field(default_factory=list)
    total_amount: float = 0.0
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PickingTaskLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    sales_order_line_id: str
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    location_id: Optional[str] = None
    location_code: Optional[str] = None
    quantity: float
    picked_qty: float = 0.0
    discrepancy_qty: float = 0.0
    scanned: bool = False
    notes: Optional[str] = None


class PickingTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    sales_order_id: str
    sales_order_number: Optional[str] = None
    warehouse_id: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    lines: List[PickingTaskLine] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PackingRecordLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    product_id: str
    sku: Optional[str] = None
    quantity: float
    packed_qty: float = 0.0


class PackingRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    sales_order_id: str
    sales_order_number: Optional[str] = None
    warehouse_id: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    package_count: int = 1
    total_weight_kg: Optional[float] = None
    lines: List[PackingRecordLine] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ShipmentLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    sales_order_line_id: Optional[str] = None
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    quantity: float
    unit: str = "PCS"
    batch_number: Optional[str] = None


class Shipment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    sales_order_id: str
    sales_order_number: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    warehouse_id: str
    status: ShipmentStatus = ShipmentStatus.DRAFT
    carrier_name: Optional[str] = None
    tracking_reference: Optional[str] = None
    shipped_date: Optional[datetime] = None
    delivered_date: Optional[datetime] = None
    lines: List[ShipmentLine] = Field(default_factory=list)
    posted: bool = False
    posted_at: Optional[datetime] = None
    posted_by: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# INVENTORY
# ============================================================================

class InventoryBalance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    warehouse_id: str
    location_id: str
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    unit: str = "PCS"
    quantity_on_hand: float = 0.0
    quantity_reserved: float = 0.0
    quantity_available: float = 0.0
    quantity_damaged: float = 0.0
    quantity_quarantine: float = 0.0
    quantity_in_transit: float = 0.0
    average_cost: float = 0.0
    total_value: float = 0.0
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    version: int = 0
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class InventoryReservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    warehouse_id: str
    location_id: Optional[str] = None
    product_id: str
    sales_order_id: Optional[str] = None
    sales_order_line_id: Optional[str] = None
    quantity: float
    status: str = "active"  # active | consumed | released
    expires_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StockLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    warehouse_id: str
    location_id: Optional[str] = None
    product_id: str
    sku: Optional[str] = None
    movement_type: StockMovementType
    quantity: float  # signed: + increases, - decreases
    quantity_before: float = 0.0
    quantity_after: float = 0.0
    unit_cost: float = 0.0
    total_cost: float = 0.0
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    reference_number: Optional[str] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    reversal_of: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class StockAdjustment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    warehouse_id: str
    location_id: str
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    adjustment_type: str = "increase"  # increase | decrease
    quantity: float
    unit_cost: float = 0.0
    reason: AdjustmentReason = AdjustmentReason.OTHER
    reason_notes: Optional[str] = None
    status: str = "draft"  # draft | pending_approval | approved | rejected | posted
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    posted: bool = False
    posted_at: Optional[datetime] = None
    ledger_entry_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StockTransferLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    requested_qty: float
    dispatched_qty: float = 0.0
    received_qty: float = 0.0
    damaged_qty: float = 0.0
    unit: str = "PCS"
    batch_number: Optional[str] = None
    notes: Optional[str] = None


class StockTransfer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    from_warehouse_id: str
    from_location_id: Optional[str] = None
    to_warehouse_id: str
    to_location_id: Optional[str] = None
    status: TransferStatus = TransferStatus.DRAFT
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    requested_date: datetime = Field(default_factory=utcnow)
    dispatched_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    lines: List[StockTransferLine] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CycleCountLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    product_id: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    location_id: Optional[str] = None
    location_code: Optional[str] = None
    system_qty: float = 0.0
    counted_qty: Optional[float] = None
    variance_qty: float = 0.0
    unit: str = "PCS"
    counted: bool = False
    notes: Optional[str] = None


class CycleCount(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    number: str
    warehouse_id: str
    location_id: Optional[str] = None
    status: CycleCountStatus = CycleCountStatus.DRAFT
    count_type: str = "location"  # location | products | full
    assigned_to: Optional[str] = None
    lines: List[CycleCountLine] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    posted: bool = False
    posted_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ============================================================================
# AUDIT / IDEMPOTENCY
# ============================================================================

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    description: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class IdempotencyRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tenant_id: str
    key: str
    endpoint: str
    request_hash: Optional[str] = None
    response: Optional[Dict[str, Any]] = None
    status_code: int = 200
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: Optional[datetime] = None


# ============================================================================
# REQUEST MODELS
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class TenantCreate(BaseModel):
    name: str
    code: str
    timezone: str = "Asia/Jakarta"
    currency: str = "IDR"
    owner_email: str
    owner_name: str
    owner_password: str
    plan_code: str = "starter"


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class PaginatedResponse(BaseModel):
    items: List[Any] = Field(default_factory=list)
    meta: PaginationMeta = Field(default_factory=PaginationMeta)
