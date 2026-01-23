---
name: webapp-testing
description: Toolkit for interacting with and testing local web applications using Playwright. Supports verifying frontend functionality, debugging UI behavior, capturing browser screenshots, and viewing browser logs.
---

# Web Application Testing

## Workflow Integration

**Before starting web app testing:**
1.  **Check Existing Code**: Use the `review-existing-code-references-skill` to check `existing-code-for-reference.md`. Look for existing tests or scripts that can be reused.
2.  **Update References**: If you create a new reusable test script, use the `review-existing-code-references-skill` to add it to the reference file.

This skill enables comprehensive testing and debugging of local web applications using Playwright automation.

## When to Use This Skill

Use this skill when you need to:
- Test frontend functionality in a real browser
- Verify UI behavior and interactions
- Debug web application issues
- Capture screenshots for documentation or debugging
- Inspect browser console logs
- Validate form submissions and user flows
- Check responsive design across viewports

## Prerequisites

- Node.js installed on the system
- A locally running web application (or accessible URL)
- **For Flutter Web App**: 建議使用 `start_flutter_skill` 啟動於端口 8899
  ```bash
  # 在獨立 CMD 中快速啟動（3-5秒）
  start cmd.exe /k "cd /d C:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App && python test/playwright-test/flutter_quick_start.py"
  ```
- Playwright will be installed automatically if not present

## Core Capabilities

### 1. Browser Automation
- Navigate to URLs
- Click buttons and links
- Fill form fields
- Select dropdowns
- Handle dialogs and alerts

### 2. Verification
- Assert element presence
- Verify text content
- Check element visibility
- Validate URLs
- Test responsive behavior

### 3. Debugging
- Capture screenshots
- View console logs
- Inspect network requests
- Debug failed tests

## Usage Examples

### Example 1: Basic Navigation Test
```javascript
// Navigate to a page and verify title
await page.goto('http://localhost:3000');
const title = await page.title();
console.log('Page title:', title);
```

### Example 2: Form Interaction
```javascript
// Fill out and submit a form
await page.fill('#username', 'testuser');
await page.fill('#password', 'password123');
await page.click('button[type="submit"]');
await page.waitForURL('**/dashboard');
```

### Example 3: Screenshot Capture
```javascript
// Capture a screenshot for debugging
await page.screenshot({ path: 'debug.png', fullPage: true });
```

## Guidelines

1. **Always verify the app is running** - Check that the local server is accessible before running tests
2. **Use explicit waits** - Wait for elements or navigation to complete before interacting
3. **Capture screenshots on failure** - Take screenshots to help debug issues
4. **Clean up resources** - Always close the browser when done
5. **Handle timeouts gracefully** - Set reasonable timeouts for slow operations
6. **Test incrementally** - Start with simple interactions before complex flows
7. **Use selectors wisely** - Prefer data-testid or role-based selectors over CSS classes

## Common Patterns

### Pattern: Wait for Element
```javascript
await page.waitForSelector('#element-id', { state: 'visible' });
```

### Pattern: Check if Element Exists
```javascript
const exists = await page.locator('#element-id').count() > 0;
```

### Pattern: Get Console Logs
```javascript
page.on('console', msg => console.log('Browser log:', msg.text()));
```

### Pattern: Handle Errors
```javascript
try {
  await page.click('#button');
} catch (error) {
  await page.screenshot({ path: 'error.png' });
  throw error;
}
```

## Limitations

- Requires Node.js environment
- Cannot test native mobile apps (use React Native Testing Library instead)
- May have issues with complex authentication flows
- Some modern frameworks may require specific configuration