import sys
import os

# Ensure the app root is in PYTHONPATH
sys.path.append(os.getcwd())

from scoring import call_ai_with_fallback, SYSTEM_PROMPT

def check_ai_health():
    print("🤖 ResuMate AI Connection Health Check")
    print("======================================")
    
    # 1. Validate environment
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY is not set in environment or .env.")
        print("   Please check your .env file and ensure it is populated.")
        sys.exit(1)
        
    print("✅ API Key found in environment.")
    
    # 2. Test Live Connection
    print("\nTesting Live connection to OpenRouter...")
    user_prompt = "Say 'Hello' back to confirm connection."
    
    try:
        # call_ai_with_fallback will try multiple models
        res = call_ai_with_fallback(SYSTEM_PROMPT, user_prompt)
        print("\n✅ AI Connection Succeeded!")
        print(f"Sample response keys found: {list(res.keys())}")
        print("\n🎉 Health Check Passed!")
        
    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")
        print("\nTroubleshooting Tips:")
        print("- Verify your key starts with `sk-or-` if using OpenRouter.")
        print("- Check if you are behind a corporate firewall/VPN.")
        print("- Verify internet access to `openrouter.ai` from this terminal.")
        sys.exit(1)

if __name__ == "__main__":
    check_ai_health()
