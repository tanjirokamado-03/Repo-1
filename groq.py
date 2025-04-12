# groq.py

import openai
from dotenv import load_dotenv
import os
import json
from typing import List, Dict, Any, Union

load_dotenv()

openai.api_key = os.getenv("GROQ_API_KEY")
openai.api_base = "https://api.groq.com/openai/v1"

def summarize_text(text: str) -> str:
    """Generate a concise summary of email text using Groq AI"""
    try:
        # For very long emails, truncate to save tokens
        truncated_text = text[:2500]  # Limit to 2500 characters for reasonable token usage
        
        response = openai.ChatCompletion.create(
            model="llama3-8b-8192",
            messages=[{
                "role": "user",
                "content": f"Summarize this email in 1-2 sentences. Keep only key information. If it's a code or OTP, mention that explicitly.\n\n{truncated_text}"
            }],
            max_tokens=150  # Limit response length to save tokens
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Groq API Error: {e}")
        return "Summary unavailable"

def analyze_and_tag_email(text: str, subject: str) -> List[Union[str, Dict[str, Any]]]:
    """Analyze email content and assign relevant tags with confidence levels"""
    try:
        # For very long emails, use just the beginning and subject for tagging
        text_sample = subject + "\n\n" + text[:1500]  # Limit to 1500 characters for reasonable token usage
        
        prompt = f"""
        Analyze this email and assign ONLY the most relevant tags from the following list:
        - academic (for coursework, assignments, lectures, projects)
        - sports (for sports activities, games, tournaments)
        - event (for campus events, seminars, meetings)
        - club (for student clubs and organizations)
        - admin (for administrative announcements)
        - deadline (for submissions, applications with deadlines)
        - urgent (for time-sensitive matters)
        - low (for low-priority informational emails)

        Return the tags as a JSON array of objects, each with "name" and "confidence" (0.0-1.0) properties.
        Limit to max 3 most relevant tags. Be precise with your analysis.

        Subject: {subject}

        Email excerpt:
        {text_sample}
        """
        
        response = openai.ChatCompletion.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150  # Limit response length
        )
        
        content = response.choices[0].message.content.strip()
        
        try:
            # Try to parse as JSON array
            tags = json.loads(content)
            if isinstance(tags, list):
                return tags
        except json.JSONDecodeError:
            # If JSON parsing fails, extract tags from text
            content = content.lower()
            
            # Find all potential tags in the response
            potential_tags = []
            tag_names = ["academic", "sports", "event", "club", "admin", "deadline", "urgent", "low"]
            
            for tag in tag_names:
                if tag in content:
                    potential_tags.append(tag)
            
            # If no tags found in the expected categories, use fallback
            if not potential_tags:
                # Default tag based on subject line keywords
                if any(kw in subject.lower() for kw in ["deadline", "due", "submit"]):
                    return ["deadline"]
                elif any(kw in subject.lower() for kw in ["urgent", "important", "asap"]):
                    return ["urgent"]
                else:
                    return ["general"]
            
            return potential_tags
            
    except Exception as e:
        print(f"⚠️ Tag Generation Error: {e}")
        return ["general"]

def generate_smart_replies(email_content: str, tags: List[Dict[str, Any]]) -> List[str]:
    """Generate context-aware smart reply suggestions"""
    try:
        # Extract tag names for prompt
        tag_names = [tag["name"] for tag in tags] if isinstance(tags[0], dict) else tags
        
        # Truncate email content
        truncated_content = email_content[:1000]
        
        prompt = f"""
        Generate 3 brief, contextually relevant reply suggestions for this email.
        Each reply should be 1-2 sentences and sound natural.
        The email has these tags: {', '.join(tag_names)}
        
        Email: {truncated_content}
        
        Return ONLY the 3 replies as a JSON array of strings.
        """
        
        response = openai.ChatCompletion.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        
        content = response.choices[0].message.content.strip()
        
        try:
            # Try to parse JSON
            replies = json.loads(content)
            if isinstance(replies, list) and len(replies) > 0:
                # Limit to 3 replies
                return replies[:3]
        except:
            pass
        
        # Fallback options based on tags
        if "urgent" in tag_names:
            return [
                "Thank you for the urgent notification. I'll address this right away.",
                "I've received your urgent message and will respond promptly.",
                "Thanks for bringing this to my attention. I'll look into it immediately."
            ]
        elif "academic" in tag_names:
            return [
                "Thank you for the academic information. I'll review it carefully.",
                "I appreciate the update on the coursework. I'll complete it on time.",
                "Thanks for sharing this academic resource. It will be helpful."
            ]
        elif "deadline" in tag_names:
            return [
                "I've noted the deadline and will ensure timely submission.",
                "Thank you for the reminder about the deadline.",
                "I'll make sure to complete this before the deadline."
            ]
        elif "event" in tag_names:
            return [
                "Thanks for the invitation. I'm looking forward to attending.",
                "Thank you for sharing the event details. I'll add it to my calendar.",
                "The event sounds interesting. Please count me in."
            ]
        else:
            return [
                "Thank you for your email. I'll get back to you soon.",
                "I appreciate you reaching out. I'll review this carefully.",
                "Thanks for sharing this information."
            ]
            
    except Exception as e:
        print(f"⚠️ Smart Reply Generation Error: {e}")
        return [
            "Thank you for your email.",
            "I'll get back to you soon.",
            "Thanks for reaching out."
        ]
