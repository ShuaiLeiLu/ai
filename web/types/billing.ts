export type MembershipLevel = 'FREE' | 'VIP1' | 'VIP2' | 'VIP3';

export interface MembershipInfo {
  level: MembershipLevel;
  display_name: string;
  battery_discount: number;
  unlocked_features: string[];
}

export interface BatteryLedgerItem {
  item_id: string;
  change: number;
  reason: string;
  created_at: string;
}

export interface BatteryPackage {
  package_id: string;
  name: string;
  battery_count: number;
  price: number;
}

