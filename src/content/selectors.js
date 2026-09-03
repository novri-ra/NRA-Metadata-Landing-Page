// Centralized DOM selectors for NRA DreamLab
// ponytail: removed unused XPath selectors (BUSY_WARNING, STATIC_WARNING, STYLE_TRIGGER, RATIO_TRIGGER, MONTHLY_LIMIT_WARNING); add back if Canva changes detection strategy
const CANVA_SELECTORS = {
  PROMPT_TEXTAREA:
    'textarea[placeholder*="Describe"], textarea[placeholder*="Ceritakan"], textarea[aria-label*="prompt" i], textarea[class*="canva-ai-input"]',
  SUBMIT_BUTTON: 'button[type="submit"]',
  DOWNLOAD_BUTTON:
    'button[aria-label*="Download" i], button[aria-label*="Unduh" i], button:has(svg path[d*="m11.25 15.85"])'
// ALERT_STATUS: '[@role="alert" or @role="status"]'
};
