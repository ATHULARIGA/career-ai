import requests
import logging
from bs4 import BeautifulSoup
from features.shared import call_ai_with_fallback

logger = logging.getLogger("resumate")

def scrape_job_link(url: str) -> dict:
    if not url:
        return {"text": "", "error": "No URL provided."}
    
    UNSUPPORTED_DOMAINS = ["linkedin.com", "indeed.com", "glassdoor.com"]
    if any(d in url.lower() for d in UNSUPPORTED_DOMAINS):
        return {"text": "", "error": "LinkedIn/Indeed/Glassdoor require login — please paste the JD text directly."}
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code >= 400:
            return {"text": "", "error": f"Could not access URL (Status {response.status_code})."}
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        content_node = None
        if "greenhouse.io" in url.lower():
            content_node = soup.select_one(".job-body, #content, #main")
        elif "lever.co" in url.lower():
            content_node = soup.select_one(".section-wrapper, .content, .job-info")
            
        if content_node:
            soup = content_node 
            
        for script_or_style in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe"]):
            script_or_style.decompose()
            
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        if len(text.strip()) < 120:
            return {"text": "", "error": "Could not extract a readable description — try pasting the text manually instead."}
            
        return {"text": text[:15000], "error": None}
    except requests.Timeout:
        return {"text": "", "error": "Request timed out (8s limit). Page took too long to load."}
    except Exception as e:
        logger.warning("Scraping failed for %s: %s", url, e)
        return {"text": "", "error": f"Scraping failed: {str(e)}"}

def clean_scraped_jd(scraped_text: str) -> str:
    """Uses lightweight AI to distill full innerText into pure requirements."""
    system = "You are an expert HR assistant. Extract ONLY the Job Title, Core Responsibilities, and Mandatory Skills/Requirements from the following text. Do not include navigation links, footer noise, or generic company boilerplate. Keep it concise."
    user = f"Scraped Text:\n\n{scraped_text[:6000]}"
    
    try:
        content = call_ai_with_fallback(system, user, temperature=0)
        if isinstance(content, str) and len(content.strip()) > 50:
             return content.strip()
        elif isinstance(content, dict):
             # If it parsed as JSON, just return stringified or extract text
             return json.dumps(content)
    except Exception as e:
        print(f"JD Clean FAILED: {e}")
            
    return scraped_text
