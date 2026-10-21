import type { Platform, SkillDefinition } from './types.js';

/**
 * The skills the router may choose, and the phrases that choose them.
 *
 * Each entry names a real SKILL.md (`<library root>/<skillName>/SKILL.md`); the
 * registry refuses to load one that is missing. Order breaks ties.
 */

/** Something in the request has to be about paid advertising before an `/ads` skill takes it. */
const AD_TERMS = [
  'google ads', 'adwords', 'meta ads', 'facebook ads', 'instagram ads', 'youtube ads', 'linkedin ads',
  'tiktok ads', 'microsoft ads', 'bing ads', 'ppc', 'paid ads', 'paid media', 'paid search', 'campaign',
  'campaigns', '廣告', '投放', '關鍵字廣告', '廣告活動',
] as const;

export const DEFAULT_CATALOG: readonly SkillDefinition[] = [
  {
    id: 'claude-ads:ads-audit',
    library: 'claude-ads',
    skillName: 'ads-audit',
    command: '/ads audit',
    summary: 'Read-only, source-grounded audit of one or more ad accounts',
    platforms: ['google_ads', 'meta_ads', 'youtube_ads', 'linkedin_ads', 'tiktok_ads', 'microsoft_ads'],
    keywords: [
      'audit', 'health check', 'account health', 'performance review', 'review', 'diagnose', 'performance',
      '審計', '稽核', '健檢', '檢查', '診斷', '表現', '成效', '廣告帳戶',
    ],
    requireAll: [AD_TERMS],
    takesPlatformScope: true,
  },
  {
    id: 'claude-ads:ads-optimize',
    library: 'claude-ads',
    skillName: 'ads-optimize',
    command: '/ads optimize',
    summary: 'Optimisation proposals for ad accounts, emitted as drafts',
    platforms: ['google_ads', 'meta_ads', 'youtube_ads', 'linkedin_ads', 'tiktok_ads', 'microsoft_ads'],
    keywords: [
      'optimize', 'optimise', 'optimization', 'bid', 'bids', 'negative keyword', 'negative keywords',
      'search terms', 'cpa', 'roas', 'pause', '優化', '出價', '否定關鍵字', '搜尋字詞', '暫停',
    ],
    requireAll: [AD_TERMS],
    ownsChanges: true,
  },
  {
    id: 'claude-ads:ads-competitor',
    library: 'claude-ads',
    skillName: 'ads-competitor',
    command: '/ads competitor',
    summary: 'Competitor ad intelligence from public transparency sources',
    platforms: ['google_ads', 'meta_ads'],
    keywords: ['competitor', 'competitors', 'ad library', 'transparency center', '競爭對手', '競品', '廣告資料庫'],
    requireAll: [AD_TERMS],
  },
  {
    id: 'claude-ads:ads-budget',
    library: 'claude-ads',
    skillName: 'ads-budget',
    command: '/ads budget',
    summary: 'Budget allocation, bidding strategy and pacing',
    platforms: ['google_ads', 'meta_ads', 'youtube_ads', 'linkedin_ads', 'tiktok_ads', 'microsoft_ads'],
    keywords: ['budget', 'pacing', 'spend allocation', '預算', '花費', '分配'],
    requireAll: [AD_TERMS],
  },
  {
    id: 'claude-ads:ads-attribution',
    library: 'claude-ads',
    skillName: 'ads-attribution',
    command: '/ads attribution',
    summary: 'Conversion definitions, attribution windows and GA4 reconciliation',
    platforms: ['google_ads', 'meta_ads', 'ga4'],
    keywords: ['attribution', 'conversion tracking', 'conversion window', '歸因', '轉換追蹤'],
  },
  {
    id: 'claude-ads:ads-landing',
    library: 'claude-ads',
    skillName: 'ads-landing',
    command: '/ads landing',
    summary: 'Landing-page audit for paid traffic',
    platforms: ['website'],
    keywords: ['landing page', 'landing pages', '到達頁', '著陸頁', '登陸頁'],
    requireAll: [AD_TERMS],
  },
  {
    id: 'notfair:seo-analysis',
    library: 'notfair',
    skillName: 'seo-analysis',
    command: '/seo-analysis',
    summary: 'Full SEO audit: Search Console, URL inspection, PageSpeed, crawl and on-page checks',
    platforms: ['search_console', 'website'],
    keywords: [
      'seo', 'technical seo', 'organic', 'organic traffic', 'search ranking', 'search rankings', 'core web vitals',
      'lighthouse', 'indexing', 'crawl errors', '搜尋排名', '自然流量', '自然搜尋', '網站排名', '索引', '關鍵字排名',
    ],
  },
  {
    id: 'notfair:google-analytics',
    library: 'notfair',
    skillName: 'google-analytics',
    command: '/google-analytics',
    summary: 'GA4 traffic, acquisition, engagement and conversion analysis',
    platforms: ['ga4'],
    keywords: [
      'ga4', 'google analytics', 'traffic', 'sessions', 'engagement', 'conversion rate', 'acquisition',
      '流量', '工作階段', '跳出率', '參與度', '轉換率', '流量來源',
    ],
  },
  {
    id: 'notfair:search-console',
    library: 'notfair',
    skillName: 'search-console',
    command: '/search-console',
    summary: 'Search Console queries, impressions, clicks and CTR',
    platforms: ['search_console'],
    keywords: ['search console', 'gsc', 'impressions', 'ctr', 'click-through rate', '搜尋成效', '曝光', '點閱率'],
    subsumedBy: ['notfair:seo-analysis'],
  },
  {
    id: 'notfair:keyword-research',
    library: 'notfair',
    skillName: 'keyword-research',
    command: '/keyword-research',
    summary: 'Keyword ideas, search volume and difficulty',
    platforms: ['website'],
    keywords: ['keyword research', 'keyword ideas', 'search volume', '關鍵字研究', '關鍵字建議', '搜尋量'],
  },
  {
    id: 'notfair:backlink-audit',
    library: 'notfair',
    skillName: 'backlink-audit',
    command: '/backlink-audit',
    summary: 'Backlink profile audit',
    platforms: ['website'],
    keywords: ['backlink', 'backlinks', 'link profile', '反向連結', '外部連結'],
  },
];

/** Names in the input that point at one ad platform, and the scope word Claude Ads uses for it. */
export const AD_PLATFORM_TERMS: ReadonlyArray<{ platform: Platform; scope: string; terms: readonly string[] }> = [
  { platform: 'google_ads', scope: 'google', terms: ['google ads', 'adwords', 'google 廣告', 'google廣告'] },
  {
    platform: 'meta_ads',
    scope: 'meta',
    terms: ['meta ads', 'facebook ads', 'instagram ads', 'meta 廣告', 'meta廣告', 'facebook 廣告', 'fb 廣告', 'fb廣告'],
  },
  { platform: 'youtube_ads', scope: 'youtube', terms: ['youtube ads', 'youtube 廣告', 'youtube廣告'] },
  { platform: 'linkedin_ads', scope: 'linkedin', terms: ['linkedin ads', 'linkedin 廣告', 'linkedin廣告'] },
  { platform: 'tiktok_ads', scope: 'tiktok', terms: ['tiktok ads', 'tiktok 廣告', 'tiktok廣告'] },
  { platform: 'microsoft_ads', scope: 'microsoft', terms: ['microsoft ads', 'bing ads', 'microsoft 廣告'] },
];

/**
 * Verbs that ask for something to be changed. A false positive only turns analysis
 * into a draft, which is harmless, so the list errs on the side of matching.
 */
export const CHANGE_TERMS = [
  'apply', 'pause', 'enable', 'disable', 'delete', 'remove', 'increase', 'decrease', 'raise', 'lower',
  'change', 'edit', 'update', 'launch', 'create campaign', 'set up', 'add negative',
  '調整', '修改', '變更', '暫停', '停用', '啟用', '刪除', '移除', '提高', '降低', '增加', '減少', '新增', '上線',
  '套用', '改成',
] as const;

export const COMPETITOR_TERMS = ['competitor', 'competitors', '競爭對手', '競品', '對手'] as const;
