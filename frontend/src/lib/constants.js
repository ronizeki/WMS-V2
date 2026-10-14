/** Shared enum values and label maps mirroring the backend domain model. */

export const PRODUCT_STATUSES = ['active', 'inactive', 'discontinued', 'draft'];
export const PRODUCT_TYPES = ['finished_good', 'raw_material', 'component', 'consumable', 'spare_part'];
export const LOCATION_TYPES = [
  'receiving',
  'storage',
  'picking',
  'shipping',
  'quarantine',
  'returns',
  'damages',
  'reserved',
];
export const LOCATION_STATUSES = ['available', 'in_use', 'blocked', 'maintenance'];
export const WAREHOUSE_STATUSES = ['active', 'inactive', 'closed'];
export const USER_STATUSES = ['active', 'inactive', 'pending', 'blocked'];
export const TENANT_STATUSES = ['active', 'inactive', 'suspended', 'trial'];

export const PO_STATUSES = ['draft', 'pending', 'approved', 'partially_received', 'received', 'closed', 'cancelled'];
export const RECEIPT_STATUSES = ['draft', 'in_progress', 'completed', 'cancelled'];
export const PUTAWAY_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled'];
export const SO_STATUSES = [
  'draft',
  'confirmed',
  'allocated',
  'picking',
  'picked',
  'packing',
  'packed',
  'partially_shipped',
  'shipped',
  'closed',
  'cancelled',
];
export const SHIPMENT_STATUSES = ['draft', 'ready', 'in_transit', 'delivered', 'partially_delivered', 'cancelled'];
export const TRANSFER_STATUSES = [
  'draft',
  'requested',
  'approved',
  'in_transit',
  'partially_received',
  'completed',
  'cancelled',
];
export const CYCLE_COUNT_STATUSES = [
  'draft',
  'in_progress',
  'pending_approval',
  'approved',
  'rejected',
  'completed',
  'cancelled',
];
export const TASK_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled'];
export const TASK_PRIORITIES = ['low', 'medium', 'high', 'urgent'];
export const ADJUSTMENT_REASONS = [
  'damage',
  'loss',
  'found',
  'expiry',
  'data_correction',
  'quality_control',
  'return',
  'other',
];
export const MOVEMENT_TYPES = [
  'inbound_receipt',
  'outbound_shipment',
  'transfer_in',
  'transfer_out',
  'adjustment_in',
  'adjustment_out',
  'putaway',
  'picking',
  'return_in',
  'return_out',
  'cycle_count_adjustment',
  'damaged',
  'quarantine',
  'unquarantine',
  'expired',
  'reversal',
];

/** Map an enum value to a Tailwind badge palette. */
export const STATUS_TONES = {
  // generic
  active: 'green',
  inactive: 'slate',
  draft: 'slate',
  pending: 'amber',
  in_progress: 'blue',
  completed: 'green',
  cancelled: 'red',
  closed: 'slate',
  // orders / fulfilment
  confirmed: 'blue',
  allocated: 'indigo',
  picking: 'indigo',
  picked: 'blue',
  packing: 'indigo',
  packed: 'blue',
  partially_shipped: 'amber',
  shipped: 'green',
  // receipts / transfers
  requested: 'amber',
  approved: 'green',
  in_transit: 'blue',
  partially_received: 'amber',
  // cycle counts
  pending_approval: 'amber',
  rejected: 'red',
  // shipments
  ready: 'blue',
  delivered: 'green',
  partially_delivered: 'amber',
  // tenant
  suspended: 'red',
  trial: 'amber',
};
