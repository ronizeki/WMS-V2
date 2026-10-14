from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


# Enums
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


class SubscriptionBillingCycle(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BLOCKED = "blocked"


class PermissionCategory(str, Enum):
    DASHBOARD = "dashboard"
    PRODUCTS = "products"
    INVENTORY = "inventory"
    WAREHOUSES = "warehouses"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TRANSFERS = "transfers"
    STOCKTAKE = "stocktake"
    REPORTS = "reports"
    USERS = "users"
    ROLES = "roles"
    TENANTS = "tenants"
    SUBSCRIPTIONS = "subscriptions"
    SETTINGS = "settings"
    AUDIT = "audit"
    API = "api"


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
    CANCELLED = "cancelled"


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


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# Base Models
class TenantBase(BaseModel):
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
    settings: Dict[str, Any] = Field(default_factory=dict)


class Tenant(TenantBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SubscriptionPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str
    price: float = 0.0
    billing_cycle: SubscriptionBillingCycle = SubscriptionBillingCycle.MONTHLY
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    plan_id: str
    status: SubscriptionStatus = SubscriptionStatus.TRIAL
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    amount: float = 0.0
    currency: str = "IDR"
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    auto_renew: bool = True
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
