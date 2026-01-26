"""
Communication MCP Provider

Handles Gmail, Telegram, and messaging integrations.
Provides secure email and messaging capabilities for the Agentic RAG system.
"""

import os
import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class CommunicationConfig(ProviderConfig):
    """Configuration for communication provider"""
    # Gmail settings
    gmail_credentials_path: Optional[str] = None
    gmail_token_path: Optional[str] = "./data/gmail_token.json"
    gmail_scopes: List[str] = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly"
    ]
    # Telegram settings
    telegram_bot_token: Optional[str] = None
    telegram_default_chat_id: Optional[str] = None
    # Human-in-the-loop (HITL) settings
    require_confirmation: bool = True
    max_recipients: int = 10


class CommunicationProvider(BaseProvider):
    """
    MCP Provider for email and messaging operations.
    
    Capabilities:
    - Gmail: Send/receive emails (requires OAuth2)
    - Telegram: Send messages via bot
    - WhatsApp: Business API integration (requires Meta approval)
    
    Security:
    - HITL confirmation for sensitive operations
    - Rate limiting
    - Recipient validation
    """
    
    def __init__(self, config: CommunicationConfig = None):
        super().__init__(config or CommunicationConfig())
        self.config: CommunicationConfig = self.config
        self._gmail_service = None
        self._telegram_bot = None
        
    async def initialize(self) -> bool:
        """Initialize the communication provider"""
        try:
            # Initialize Gmail if credentials available
            if self.config.gmail_credentials_path:
                await self._init_gmail()
            
            # Initialize Telegram if token available
            if self.config.telegram_bot_token:
                await self._init_telegram()
            
            self._initialized = True
            logger.info("CommunicationProvider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CommunicationProvider: {e}")
            return False
    
    async def _init_gmail(self):
        """Initialize Gmail API client"""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            creds = None
            
            # Load existing token
            if os.path.exists(self.config.gmail_token_path):
                creds = Credentials.from_authorized_user_file(
                    self.config.gmail_token_path, 
                    self.config.gmail_scopes
                )
            
            # Refresh or create new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.config.gmail_credentials_path,
                        self.config.gmail_scopes
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save credentials
                os.makedirs(os.path.dirname(self.config.gmail_token_path) or '.', exist_ok=True)
                with open(self.config.gmail_token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self._gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail service initialized")
            
        except ImportError:
            logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail: {e}")
    
    async def _init_telegram(self):
        """Initialize Telegram bot"""
        try:
            from telegram import Bot
            self._telegram_bot = Bot(token=self.config.telegram_bot_token)
            logger.info("Telegram bot initialized")
        except ImportError:
            logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram: {e}")
    
    async def health_check(self) -> bool:
        """Check if provider is healthy"""
        gmail_ok = self._gmail_service is not None
        telegram_ok = self._telegram_bot is not None
        
        self._is_healthy = gmail_ok or telegram_ok
        self._last_health_check = datetime.now()
        return self._is_healthy
    
    def get_capabilities(self) -> List[str]:
        """List available operations"""
        caps = []
        if self._gmail_service:
            caps.extend(["send_email", "read_emails", "search_emails"])
        if self._telegram_bot:
            caps.extend(["send_telegram", "send_telegram_photo"])
        return caps
    
    # ==================== Gmail Operations ====================
    
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        body: str,
        cc: List[str] = None,
        html: bool = False,
        confirm: bool = None
    ) -> ProviderResult:
        """Send an email via Gmail API"""
        if not self._gmail_service:
            return ProviderResult(
                success=False,
                error="Gmail not configured. Provide credentials_path.",
                provider=self.provider_name,
                operation="send_email"
            )
        
        # HITL confirmation check
        should_confirm = confirm if confirm is not None else self.config.require_confirmation
        if should_confirm:
            logger.info(f"[HITL] Email pending confirmation: To={to}, Subject={subject}")
            return ProviderResult(
                success=False,
                error="HITL_REQUIRED",
                data={
                    "action": "send_email",
                    "to": to,
                    "subject": subject,
                    "body_preview": body[:200],
                    "message": "Human confirmation required before sending"
                },
                provider=self.provider_name,
                operation="send_email"
            )
        
        try:
            # Create message
            if html:
                message = MIMEMultipart('alternative')
                message.attach(MIMEText(body, 'html'))
            else:
                message = MIMEText(body)
            
            message['to'] = to
            message['subject'] = subject
            
            if cc:
                message['cc'] = ', '.join(cc)
            
            # Encode message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send via API
            result = self._gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            return ProviderResult(
                success=True,
                data={
                    "message_id": result.get('id'),
                    "thread_id": result.get('threadId'),
                    "to": to,
                    "subject": subject
                },
                provider=self.provider_name,
                operation="send_email"
            )
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="send_email"
            )
    
    async def read_emails(
        self, 
        max_results: int = 10,
        label: str = "INBOX",
        unread_only: bool = False
    ) -> ProviderResult:
        """Read recent emails from Gmail"""
        if not self._gmail_service:
            return ProviderResult(
                success=False,
                error="Gmail not configured",
                provider=self.provider_name,
                operation="read_emails"
            )
        
        try:
            query = f"in:{label.lower()}"
            if unread_only:
                query += " is:unread"
            
            # List messages
            results = self._gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            emails = []
            for msg in messages:
                # Get full message
                full_msg = self._gmail_service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in full_msg.get('payload', {}).get('headers', [])}
                
                emails.append({
                    "id": msg['id'],
                    "thread_id": msg.get('threadId'),
                    "from": headers.get('From'),
                    "subject": headers.get('Subject'),
                    "date": headers.get('Date'),
                    "snippet": full_msg.get('snippet', '')
                })
            
            return ProviderResult(
                success=True,
                data={"emails": emails, "count": len(emails)},
                provider=self.provider_name,
                operation="read_emails"
            )
            
        except Exception as e:
            logger.error(f"Error reading emails: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="read_emails"
            )
    
    async def search_emails(self, query: str, max_results: int = 10) -> ProviderResult:
        """Search emails using Gmail search syntax"""
        if not self._gmail_service:
            return ProviderResult(
                success=False,
                error="Gmail not configured",
                provider=self.provider_name,
                operation="search_emails"
            )
        
        try:
            results = self._gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            emails = []
            for msg in messages[:max_results]:
                full_msg = self._gmail_service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in full_msg.get('payload', {}).get('headers', [])}
                
                emails.append({
                    "id": msg['id'],
                    "from": headers.get('From'),
                    "subject": headers.get('Subject'),
                    "date": headers.get('Date'),
                    "snippet": full_msg.get('snippet', '')
                })
            
            return ProviderResult(
                success=True,
                data={"emails": emails, "count": len(emails), "query": query},
                provider=self.provider_name,
                operation="search_emails"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="search_emails"
            )
    
    # ==================== Telegram Operations ====================
    
    async def send_telegram(
        self, 
        text: str, 
        chat_id: str = None,
        parse_mode: str = "HTML"
    ) -> ProviderResult:
        """Send a message via Telegram bot"""
        if not self._telegram_bot:
            return ProviderResult(
                success=False,
                error="Telegram not configured. Set telegram_bot_token.",
                provider=self.provider_name,
                operation="send_telegram"
            )
        
        try:
            chat_id = chat_id or self.config.telegram_default_chat_id
            
            if not chat_id:
                return ProviderResult(
                    success=False,
                    error="No chat_id provided",
                    provider=self.provider_name,
                    operation="send_telegram"
                )
            
            message = await self._telegram_bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode
            )
            
            return ProviderResult(
                success=True,
                data={
                    "message_id": message.message_id,
                    "chat_id": chat_id,
                    "text": text[:100]
                },
                provider=self.provider_name,
                operation="send_telegram"
            )
            
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="send_telegram"
            )
    
    async def send_telegram_photo(
        self, 
        photo_path: str, 
        caption: str = None,
        chat_id: str = None
    ) -> ProviderResult:
        """Send a photo via Telegram bot"""
        if not self._telegram_bot:
            return ProviderResult(
                success=False,
                error="Telegram not configured",
                provider=self.provider_name,
                operation="send_telegram_photo"
            )
        
        try:
            chat_id = chat_id or self.config.telegram_default_chat_id
            
            with open(photo_path, 'rb') as photo:
                message = await self._telegram_bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption
                )
            
            return ProviderResult(
                success=True,
                data={"message_id": message.message_id, "chat_id": chat_id},
                provider=self.provider_name,
                operation="send_telegram_photo"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="send_telegram_photo"
            )
    
    # ==================== WhatsApp (Meta Business API) ====================
    
    async def send_whatsapp(
        self, 
        phone_number: str, 
        message: str,
        access_token: str = None,
        phone_number_id: str = None
    ) -> ProviderResult:
        """
        Send a WhatsApp message via Meta Business API.
        
        Note: Requires approved Meta Business API access.
        See: https://developers.facebook.com/docs/whatsapp/cloud-api
        """
        try:
            import requests
            
            if not access_token or not phone_number_id:
                return ProviderResult(
                    success=False,
                    error="WhatsApp Business API credentials not provided. Need access_token and phone_number_id.",
                    provider=self.provider_name,
                    operation="send_whatsapp"
                )
            
            url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {"body": message}
            }
            
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()
            
            if response.status_code == 200:
                return ProviderResult(
                    success=True,
                    data={
                        "message_id": result.get("messages", [{}])[0].get("id"),
                        "to": phone_number
                    },
                    provider=self.provider_name,
                    operation="send_whatsapp"
                )
            else:
                return ProviderResult(
                    success=False,
                    error=result.get("error", {}).get("message", "Unknown error"),
                    provider=self.provider_name,
                    operation="send_whatsapp"
                )
                
        except ImportError:
            return ProviderResult(
                success=False,
                error="requests library not installed",
                provider=self.provider_name,
                operation="send_whatsapp"
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="send_whatsapp"
            )


# Singleton instance
communication_provider = CommunicationProvider()
