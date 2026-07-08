// ============================================================
// Notification Models — synced with backend notifications/router.py
// ============================================================

// ── Single notification from GET /notifications ──────────────────────
export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  link_url?: string | null;
  is_read: boolean;
  created_at: string;
}

// ── Count from GET /notifications/count ──────────────────────────────
export interface UnreadCountResponse {
  unread_count: number;
}
