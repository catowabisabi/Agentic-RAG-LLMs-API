# API Key Error Modal Implementation

## Overview
Implemented automatic API key error detection and popup modal to allow users to input their API key when errors occur.

## 功能概述
當系統偵測到 API Key 錯誤（401 錯誤或 invalid_api_key），會自動彈出視窗要求使用者輸入 API Key。

## Implementation Details

### 1. Backend Error Detection (`services/llm_service.py`)
- Added API key error detection in the `generate()` method exception handler
- Checks for:
  - HTTP 401 errors
  - "invalid_api_key" in error message
  - "incorrect api key" in error message
- Broadcasts `api_key_error` event via WebSocket to all connected clients

```python
# Check if this is an API key error
error_str = str(e)
if "401" in error_str or "invalid_api_key" in error_str.lower() or "incorrect api key" in error_str.lower():
    # Broadcast API key error
    from services.broadcast_service import get_broadcast_service
    broadcast = get_broadcast_service()
    await broadcast.custom(
        message_type="api_key_error",
        content={
            "error": "Invalid or missing API key",
            "provider": self.provider,
            "details": error_str,
            "action_required": "Please provide a valid API key"
        }
    )
```

### 2. Configuration API Endpoint (`fast_api/routers/config_router.py`)
New router with two endpoints:

#### POST `/config/api-key`
- Update API key for a provider (openai, anthropic, google)
- Updates `.env` file in `config/` directory
- Updates environment variables and Config class
- Reinitializes LLM service with new API key

**Request:**
```json
{
  "provider": "openai",
  "api_key": "sk-proj-..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "API key for openai updated successfully",
  "provider": "openai"
}
```

#### GET `/config/api-key-status`
- Check which API keys are configured
- Returns partial key (last 8 characters) for verification
- Does not reveal full API key

### 3. Frontend Modal Component (`ui/components/APIKeyModal.tsx`)
Beautiful modal dialog with:
- Error message display
- Provider-specific instructions
- Link to OpenAI API keys page
- Password input field
- Save/Cancel buttons
- Success/Error feedback
- Dark mode support

**Features:**
- Auto-focus on input field
- Password field to hide API key
- Loading state during submission
- Success message before auto-closing
- Error handling with user-friendly messages

### 4. Chat Page Integration (`ui/components/ChatPageV2.tsx`)
Added:
- Import of APIKeyModal component
- State management for modal (isOpen, provider, errorDetails)
- WebSocket message handler for `api_key_error` events
- Modal rendering at the end of component

**WebSocket Handler:**
```typescript
if (data.type === 'api_key_error') {
  setApiKeyProvider(data.content?.provider || 'openai');
  setApiKeyError(data.content?.details || 'Invalid or missing API key');
  setShowAPIKeyModal(true);
  setLoading(false);
  setPendingInfo(null);
  return;
}
```

### 5. App Registration (`fast_api/app.py`)
- Imported config_router
- Registered router with FastAPI app

## Usage Flow

1. **User sends a query**
2. **System attempts to call LLM API**
3. **API returns 401 error (invalid key)**
4. **LLM service detects error** and broadcasts `api_key_error` event via WebSocket
5. **Frontend receives event** and shows API key modal
6. **User enters API key** in modal
7. **Frontend sends** POST request to `/config/api-key`
8. **Backend updates** `.env` file, environment variables, and Config class
9. **Backend reinitializes** LLM service with new key
10. **Modal closes** with success message
11. **User can retry** their query

## Files Modified

### Backend
- `services/llm_service.py` - Added API key error detection
- `fast_api/routers/config_router.py` - New configuration router (created)
- `fast_api/app.py` - Registered config router

### Frontend
- `ui/components/APIKeyModal.tsx` - New modal component (created)
- `ui/components/ChatPageV2.tsx` - Integrated modal and WebSocket handler

## Testing

### Test the Modal
1. Start the backend with an invalid or missing OpenAI API key
2. Open the chat interface
3. Send any message that requires LLM
4. Modal should automatically appear
5. Enter a valid API key
6. Click "Save API Key"
7. Verify the key is saved in `config/.env`
8. Try sending a message again - should work now

### Test the API Endpoint Directly
```bash
# Check current API key status
curl http://localhost:1130/config/api-key-status

# Update API key
curl -X POST http://localhost:1130/config/api-key \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-proj-YOUR_KEY_HERE"
  }'
```

## Security Considerations

1. **API keys are stored in `.env` file** - Keep this file secure and add to `.gitignore`
2. **Partial key display** - Only shows last 8 characters in status endpoint
3. **Password input field** - API key is hidden during entry
4. **No API key in logs** - Keys are not logged in the application

## Future Enhancements

1. **Encrypted storage** - Store API keys in encrypted format
2. **User-specific keys** - Support different API keys per user
3. **Key validation** - Test API key before saving
4. **Multiple providers** - Allow multiple providers with fallback
5. **Key expiration** - Warn when API keys might be expiring
6. **Usage limits** - Show remaining credits/quota

## Notes

- Modal uses Tailwind CSS for styling (dark mode compatible)
- WebSocket connection required for automatic error popup
- Backend must be restarted to fully pick up new environment variables (LLM service is reinitialized automatically)
- Compatible with all LLM providers (OpenAI, Anthropic, Google)
