import requests
import sys

def test_linkedin_scraping():
    # Use a real public LinkedIn job URL if possible, otherwise a generic one to test response headers
    url = "https://www.linkedin.com/jobs/view/4100900000" # Placeholder, let's see if we get a 200 or 999
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1"
    }
    
    print(f"Testing LinkedIn scrapability for {url} with Desktop Headers...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        
        if res.status_code == 999:
            print("❌ LinkedIn blocked request with standard 999 Security Response.")
            return False
        
        text = res.text.lower()
        if "login" in text and "password" in text:
            print("❌ Redirected to Login page.")
            return False
            
        if "description" in text or "required" in text or "skills" in text:
            print("✅ Success! Job Description data seems to be fetched!")
            return True
            
        print("❌ Loaded a page but could not find JD markers.")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_linkedin_scraping()
