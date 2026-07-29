export interface SourceResponse {
  id: string;
  canonical_name: string;
  display_name: string;
  display_name_en?: string;
  aliases: string[];
  base_url: string;
  rss_url?: string;
  language: string;
  search_language: string;
  js_rendered: boolean;
  is_active: boolean;
  description?: string;
  body_selectors: string[];
  title_selectors: string[];
  date_selectors: string[];
  internal_search_url?: string;
  article_url_patterns: string[];
  created_at: string;
  updated_at: string;
}

export interface SourceListResponse {
  items: SourceResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface SourceCreateRequest {
  canonical_name: string;
  display_name: string;
  display_name_en?: string;
  aliases?: string[];
  base_url: string;
  rss_url?: string;
  language?: string;
  search_language?: string;
  js_rendered?: boolean;
  description?: string;
  body_selectors?: string[];
  title_selectors?: string[];
  date_selectors?: string[];
  internal_search_url?: string;
  article_url_patterns?: string[];
}

export interface SourceUpdateRequest {
  display_name?: string;
  display_name_en?: string;
  aliases?: string[];
  base_url?: string;
  rss_url?: string;
  language?: string;
  search_language?: string;
  js_rendered?: boolean;
  is_active?: boolean;
  description?: string;
  body_selectors?: string[];
  title_selectors?: string[];
  date_selectors?: string[];
  internal_search_url?: string;
  article_url_patterns?: string[];
}
