// Centralized DOM selectors for Canva Auto Prompter
const CANVA_SELECTORS = {
  // Textarea selectors
  PROMPT_TEXTAREA:
    'textarea[placeholder*="Describe"], textarea[class*="canva"]',

  // Button selectors
  SUBMIT_BUTTON: 'button[type="submit"]',
  DOWNLOAD_BUTTON: 'button[aria-label="Download Image"]',

  // Alert/status selectors
  ALERT_STATUS: '[@role="alert" or @role="status"]',

  // Cooldown warning selectors
  BUSY_WARNING:
    "//*[not(@data-bot-ignored='true') and contains(text(), 'Lots of people are using Dream Lab')]",
  STATIC_WARNING:
    "//*[not(@data-bot-ignored='true') and not(ancestor-or-self::*[@role='alert' or @role='status']) and (contains(text(), 'generate again in') or contains(text(), 'Try again in'))]",

  // Configuration selectors
  STYLE_TRIGGER:
    "//*[(local-name()='button' or @role='button') and normalize-space(text())='Style']",
  RATIO_TRIGGER:
    "//*[(local-name()='button' or @role='button') and normalize-space(text())='Ratio']",

  // Monthly limit warning
  MONTHLY_LIMIT_WARNING:
    "//*[contains(text(), 'monthly AI limit') or contains(text(), 'hit your plan') or contains(text(), 'Upgrade to get more AI')]",
};
// Centralized DOM selectors for Canva Auto Prompter
const CANVA_SELECTORS = {
  // Textarea selectors
  PROMPT_TEXTAREA:
    'textarea[placeholder*="Describe"], textarea[class*="canva"]',

  // Button selectors
  SUBMIT_BUTTON: 'button[type="submit"]',
  DOWNLOAD_BUTTON:
    'button[aria-label*="Download" i], button[aria-label*="download" i], button[aria-label*="Unduh" i]',

  // Alert/status selectors
  ALERT_STATUS: '[@role="alert" or @role="status"]',

  // Cooldown warning selectors
  BUSY_WARNING:
    "//*[not(@data-bot-ignored='true') and contains(text(), 'Lots of people are using Dream Lab')]",
  STATIC_WARNING:
    "//*[not(@data-bot-ignored='true') and not(ancestor-or-self::*[@role='alert' or @role='status']) and (contains(text(), 'generate again in') or contains(text(), 'Try again in'))]",

  // Configuration selectors
  STYLE_TRIGGER:
    "//*[(local-name()='button' or @role='button') and normalize-space(text())='Style']",
  RATIO_TRIGGER:
    "//*[(local-name()='button' or @role='button') and normalize-space(text())='Ratio']",

  // Monthly limit warning
  MONTHLY_LIMIT_WARNING:
    "//*[contains(text(), 'monthly AI limit') or contains(text(), 'hit your plan') or contains(text(), 'Upgrade to get more AI')]",
};
