export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
}

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
  environment: string;
  timestamp: string;
}
