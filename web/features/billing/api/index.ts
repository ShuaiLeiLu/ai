import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import { BatteryLedgerItem, BatteryPackage, MembershipInfo } from '@/types/billing';

const API_BASE = '/billing';

export const getMembership = async (): Promise<MembershipInfo> => {
  const response = await http<ApiResponse<MembershipInfo>>(`${API_BASE}/membership`);
  return response.data;
};

export const listBatteryLedger = async (limit = 50): Promise<BatteryLedgerItem[]> => {
  const response = await http<ApiResponse<ListResponse<BatteryLedgerItem>>>(`${API_BASE}/battery/ledger?limit=${limit}`);
  return response.data.items;
};

export const listBatteryPackages = async (): Promise<BatteryPackage[]> => {
  const response = await http<ApiResponse<ListResponse<BatteryPackage>>>(`${API_BASE}/battery/packages`);
  return response.data.items;
};

