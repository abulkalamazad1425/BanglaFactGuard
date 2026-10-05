// ============================================================
// API Endpoint Constants
// ============================================================

export const API_ENDPOINTS = {
  // Auth
  AUTH_REGISTER: '/auth/register',
  AUTH_LOGIN: '/auth/login',
  AUTH_REFRESH: '/auth/refresh',
  AUTH_LOGOUT: '/auth/logout',
  AUTH_ME: '/auth/me',
  AUTH_PASSWORD_RESET_REQUEST: '/auth/password-reset/request',
  AUTH_PASSWORD_RESET_CONFIRM: '/auth/password-reset/confirm',
  AUTH_CHANGE_PASSWORD: '/auth/change-password',

  // Users
  USERS_SUBMISSIONS: '/users/me/submissions',
  USERS_SUBMISSION_STATS: '/users/me/submissions/stats',
  USERS_PROFILE: '/users/me/profile',

  // Verification
  VERIFICATION: '/verify',
  VERIFICATION_ASYNC: '/verify/async',

  // Multimodal
  MULTIMODAL_PREDICT: '/multimodal/predict',
  MULTIMODAL_BY_SUBMISSION: '/multimodal/by-submission',

  // Submissions (type-agnostic lookup — tells the caller which detail
  // endpoint above to use for a given submission_id)
  SUBMISSIONS: '/submissions',

  // Photo Card
  PHOTOCARD: '/photocard',
  PHOTOCARD_VERIFY_ASYNC: '/photocard/verify/async',

  // Expert
  EXPERT_QUEUE: '/expert/queue',
  EXPERT_HISTORY: '/expert/history',
  EXPERT_STATS: '/expert/stats',
  EXPERT_REVIEWS: '/expert/reviews',

  // Admin
  ADMIN_EXPERTS: '/admin/experts',
  ADMIN_STATS: '/admin/stats',
  ADMIN_CREDIBILITY_TIERS: '/admin/credibility-tiers',
  ADMIN_VOTING_CONFIG: '/admin/voting-config',

  // Notifications
  NOTIFICATIONS: '/notifications',
  NOTIFICATIONS_COUNT: '/notifications/count',
  NOTIFICATIONS_READ_ALL: '/notifications/read-all',

  // Dashboard (public)
  DASHBOARD_STATS: '/dashboard/stats',
  DASHBOARD_TOP_SOURCES: '/dashboard/top-sources',
  DASHBOARD_EXPLORER: '/dashboard/explorer',

  // Sources
  SOURCES: '/sources',
} as const;
