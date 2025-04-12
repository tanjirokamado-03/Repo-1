from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from email_handler.groq import summarize_text, analyze_and_tag_email
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Dict
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import os
from dotenv import load_dotenv
import time
import asyncio

# Load environment variables
load_dotenv()

# Increase imaplib buffer size to handle larger emails
imaplib._MAXLINE = 1000000

app = FastAPI(title="Grey Mail API", version="1.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

class TagWithConfidence(BaseModel):
    name: str
    confidence: float = 1.0
    color: Optional[str] = None

class EmailModel(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    subject: str
    summary: str
    date: str
    tags: List[TagWithConfidence] = []
    unread: bool = True

# Track last API call time to implement cooldown
last_api_call = 0
COOLDOWN_PERIOD = 2  # seconds between API calls

def respect_cooldown():
    """Ensure we're respecting the cooldown period between API calls"""
    global last_api_call
    current_time = time.time()
    
    if current_time - last_api_call < COOLDOWN_PERIOD:
        time.sleep(COOLDOWN_PERIOD - (current_time - last_api_call))
    
    last_api_call = time.time()

def get_email_body(msg) -> str:
    """Extract plain text body from email with improved HTML handling"""
    text = ""
    html = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
                
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    text += payload.decode(charset, errors="replace")
                except Exception as e:
                    print(f"Error decoding plain text: {e}")
                    
            elif content_type == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    html += payload.decode(charset, errors="replace")
                except Exception as e:
                    print(f"Error decoding HTML: {e}")
    else:
        # Not multipart
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            if content_type == "text/plain":
                text = payload.decode(charset, errors="replace")
            elif content_type == "text/html":
                html = payload.decode(charset, errors="replace")
        except Exception as e:
            print(f"Error decoding non-multipart message: {e}")
    
    # Prefer plain text, but use HTML if that's all we have
    return text if text else html

def fetch_emails_from_server(limit: int = 5) -> List[dict]:
    """Fetch emails from IMAP server with improved error handling"""
    try:
        # Connect to IMAP server
        with imaplib.IMAP4(os.getenv("IMAP_SERVER"), int(os.getenv("IMAP_PORT"))) as imap:
            imap.starttls()
            imap.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
            
            # Select inbox and search emails
            imap.select("inbox")
            status, messages = imap.search(None, "ALL")
            if status != "OK":
                raise Exception("Failed to search emails")
                
            email_ids = messages[0].split()
            # Get most recent emails
            email_ids_to_fetch = email_ids[-limit:] if len(email_ids) >= limit else email_ids
            
            emails = []
            for email_id in reversed(email_ids_to_fetch):  # Process newest first
                try:
                    status, msg_data = imap.fetch(email_id, "(RFC822)")
                    if status != "OK":
                        print(f"Failed to fetch email {email_id.decode()}")
                        continue
                    
                    # Parse email
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract subject with error handling
                    try:
                        subject_header = msg.get("Subject", "")
                        decoded_header = decode_header(subject_header)
                        subject = decoded_header[0][0]
                        if isinstance(subject, bytes):
                            charset = decoded_header[0][1] or 'utf-8'
                            subject = subject.decode(charset, errors='replace')
                    except Exception as e:
                        print(f"Error decoding subject: {e}")
                        subject = "[Subject encoding error]"
                    
                    # Extract body
                    body = get_email_body(msg)
                    
                    # Create email object
                    emails.append({
                        "id": email_id.decode(),
                        "from": msg.get("From", "Unknown"),
                        "subject": subject,
                        "date": msg.get("Date", ""),
                        "body": body,
                        "unread": True  # In a real implementation, check IMAP flags
                    })
                    
                except Exception as e:
                    print(f"Error processing email {email_id.decode()}: {e}")
            
            return emails
            
    except Exception as e:
        print(f"IMAP Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Email server error: {str(e)}")

def generate_summary(text: str) -> str:
    """Generate summary with cooldown respect"""
    respect_cooldown()
    return summarize_text(text)

def generate_tags(text: str, subject: str) -> List[TagWithConfidence]:
    """Generate tags with confidence scores"""
    respect_cooldown()
    
    # Call the AI-powered tagging function
    raw_tags = analyze_and_tag_email(text, subject)
    
    # Convert to TagWithConfidence objects
    tag_objects = []
    for tag in raw_tags:
        # Handle both string tags and tag objects from AI
        if isinstance(tag, dict) and "name" in tag and "confidence" in tag:
            name = tag["name"]
            confidence = tag["confidence"]
        else:
            name = tag
            confidence = 1.0
            
        # Get color for tag if available
        from email_handler.tag_manager import tag_manager
        color = tag_manager.get_tag_color(name)
        
        # Create tag object
        tag_objects.append(TagWithConfidence(
            name=name,
            confidence=confidence,
            color=color
        ))
    
    return tag_objects

async def process_email(email_data: dict) -> dict:
    """Process a single email with summary and tags"""
    try:
        # Generate summary
        summary = generate_summary(email_data["body"])
        
        # Allow a small delay between API calls
        await asyncio.sleep(0.1)
        
        # Generate tags
        tags = generate_tags(email_data["body"], email_data["subject"])
        
        return {
            "id": email_data["id"],
            "from": email_data["from"],
            "subject": email_data["subject"],
            "summary": summary,
            "date": email_data["date"],
            "tags": tags,
            "unread": email_data["unread"]
        }
    except Exception as e:
        print(f"Error processing email {email_data['id']}: {e}")
        # Return minimal info if processing fails
        return {
            "id": email_data["id"],
            "from": email_data["from"],
            "subject": email_data["subject"],
            "summary": "Error generating summary",
            "date": email_data["date"],
            "tags": [],
            "unread": email_data["unread"]
        }

# API Endpoints
@app.get("/")
def read_root():
    return {
        "name": "Grey Mail API",
        "version": "1.0",
        "status": "running",
        "endpoints": {
            "/fetch-emails": "Fetch processed emails",
            "/health": "Service health check"
        }
    }

@app.get("/fetch-emails", response_model=List[EmailModel])
async def fetch_emails(limit: int = 5, unread_only: bool = False):
    try:
        start_time = time.time()
        
        # Fetch raw emails
        raw_emails = fetch_emails_from_server(limit)
        
        # Process emails sequentially with cooldown
        processed_emails = []
        for email_data in raw_emails:
            processed_email = await process_email(email_data)
            processed_emails.append(processed_email)
        
        # Filter unread if requested
        if unread_only:
            processed_emails = [e for e in processed_emails if e["unread"]]
        
        end_time = time.time()
        print(f"Processed {len(processed_emails)} emails in {end_time - start_time:.2f} seconds")
        
        return processed_emails
    except Exception as e:
        print(f"Error in fetch_emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    try:
        # Test IMAP connection
        with imaplib.IMAP4(os.getenv("IMAP_SERVER"), int(os.getenv("IMAP_PORT"))) as imap:
            imap.starttls()
            imap.noop()  # Simple ping
        
        # Test Groq API
        api_available = os.getenv("GROQ_API_KEY") is not None
        
        return {
            "status": "healthy",
            "services": {
                "imap": "connected",
                "groq": "available" if api_available else "unconfigured"
            },
            "time": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "time": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
