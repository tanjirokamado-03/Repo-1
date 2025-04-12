# email_handler.py

import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

load_dotenv()

def decode_mime(s):
    if not s:
        return "N/A"
    parts = decode_header(s)
    return " ".join([
        part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        for part, enc in parts
    ])

def extract_body(msg):
    """Extract email body with enhanced content handling"""
    text = ""
    html = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_dispo = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_dispo:
                continue
                
            # Collect text parts
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    text += payload.decode(charset, errors="replace")
                except Exception as e:
                    print(f"Error decoding text part: {e}")
                    
            # Collect HTML parts as fallback
            elif content_type == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    html += payload.decode(charset, errors="replace")
                except Exception as e:
                    print(f"Error decoding HTML part: {e}")
    else:
        # Non-multipart message
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            if payload:
                if content_type == "text/plain":
                    text = payload.decode(charset, errors="replace")
                elif content_type == "text/html":
                    html = payload.decode(charset, errors="replace")
        except Exception as e:
            print(f"Error decoding non-multipart message: {e}")
    
    # Prefer text parts, fall back to HTML if no text
    return text or html or "[No readable content]"

def process_message(mail_id, msg_data):
    """Process a single message"""
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            try:
                msg = email.message_from_bytes(response_part[1])
                
                # Extract and decode subject
                subject_header = msg.get("Subject", "No Subject")
                subject_parts = decode_header(subject_header)
                subject = ""
                for part, charset in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(charset or 'utf-8', errors='replace')
                    else:
                        subject += part
                
                return {
                    "id": mail_id.decode() if isinstance(mail_id, bytes) else mail_id,
                    "sender": decode_mime(msg.get("From", "Unknown")),
                    "subject": subject,
                    "body": extract_body(msg),
                    "date": decode_mime(msg.get("Date", "N/A")),
                    "unread": True  # In a real implementation, you'd check flags
                }
            except Exception as e:
                print(f"Error processing message: {e}")
                return None
    return None

def fetch_emails(limit=10, filter_criteria=None):
    """Fetch emails with parallel processing"""
    try:
        # Increase buffer size
        imaplib._MAXLINE = 1000000
        
        imap = imaplib.IMAP4(os.getenv("IMAP_SERVER"), int(os.getenv("IMAP_PORT")))
        imap.starttls()
        imap.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        
        # Select inbox (or other folder if specified in filter)
        folder = "inbox"
        if filter_criteria and "folder" in filter_criteria:
            folder = filter_criteria["folder"]
        imap.select(folder)
        
        # Build search criteria
        search_criteria = "ALL"
        if filter_criteria:
            if "unread" in filter_criteria and filter_criteria["unread"]:
                search_criteria = "UNSEEN"
            elif "from" in filter_criteria:
                search_criteria = f'FROM "{filter_criteria["from"]}"'
            elif "subject" in filter_criteria:
                search_criteria = f'SUBJECT "{filter_criteria["subject"]}"'
        
        status, messages = imap.search(None, search_criteria)
        mail_ids = messages[0].split()
        
        # Get the most recent emails
        email_ids_to_fetch = mail_ids[-limit:] if mail_ids else []
        
        emails = []
        
        # Define a function to fetch a single email with retry
        def fetch_single_email(mail_id, max_retries=3):
            for attempt in range(max_retries):
                try:
                    status, msg_data = imap.fetch(mail_id, "(RFC822)")
                    if status != "OK":
                        if attempt < max_retries - 1:
                            print(f"Retry {attempt+1} for email {mail_id}...")
                            continue
                        return None
                    return process_message(mail_id, msg_data)
                except Exception as e:
                    print(f"Error on attempt {attempt+1} for email {mail_id}: {e}")
                    if attempt >= max_retries - 1:
                        break
            return None
        
        # Use ThreadPoolExecutor to fetch emails in parallel
        with ThreadPoolExecutor(max_workers=min(len(email_ids_to_fetch), 5)) as executor:
            # Submit all fetch tasks
            future_to_mail_id = {executor.submit(fetch_single_email, mail_id): mail_id for mail_id in email_ids_to_fetch}
            
            # Collect results as they complete
            for future in as_completed(future_to_mail_id):
                mail_id = future_to_mail_id[future]
                try:
                    result = future.result()
                    if result:
                        emails.append(result)
                except Exception as e:
                    print(f"Exception fetching email {mail_id}: {str(e)}")
        
        imap.logout()
        return emails
    except Exception as e:
        print(f"⚠️ IMAP Error: {e}")
        return []
