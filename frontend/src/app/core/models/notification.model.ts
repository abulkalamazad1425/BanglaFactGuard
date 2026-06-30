// ============================================================
// Notification Models
// ============================================================

export interface Notification {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  link_url: string | null;
  is_read: boolean;
  created_at: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}
