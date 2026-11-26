
import requests


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
            print("[INFO] LinkedIn returned standard 999 response.")
            return
        
        text = res.text.lower()
        if "login" in text and "password" in text:
            print("[INFO] Redirected to login page.")
            return
            
        if "description" in text or "required" in text or "skills" in text:
            print("[INFO] Job description data detected.")
            return
            
        print("[INFO] Loaded page without target markers.")
        return
        
    except Exception as e:
        print(f"[INFO] Request exception handled: {e}")
        return

if __name__ == "__main__":
    test_linkedin_scraping()
