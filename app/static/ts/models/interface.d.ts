export interface ApiResponse {
  status_code: number;
  data?: any[];
  meta?: Record<string, any>;
  error?: string;
}

export interface Post {
  id: number;
  title: string;
  start_date: string;
  end_date: string;
  status: "pending" | "in_progress" | "completed";
}
