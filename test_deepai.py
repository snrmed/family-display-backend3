#!/usr/bin/env python3
"""
Test DeepAI API connectivity from Cloud Shell
Usage: python3 test_deepai.py YOUR_API_KEY_HERE [--stream]
"""

import sys
import json
import httpx

def test_deepai_sync(api_key: str, use_stream: bool = False):
    """Test DeepAI API with detailed error reporting"""
    
    print(f"🔑 Testing DeepAI API")
    print(f"   API key: {api_key[:20]}...{api_key[-10:]}")
    print(f"   Streaming: {'ENABLED' if use_stream else 'DISABLED'}")
    print()
    
    prompt = "Write a short weather forecast for today with clear skies and 25°C in Brisbane"
    
    print(f"📝 Prompt: {prompt}")
    print()
    
    try:
        # Test 1: Basic connectivity
        print("Test 1: Checking DeepAI endpoint...")
        response = httpx.get("https://api.deepai.org/", timeout=10)
        print(f"   ✅ DeepAI endpoint reachable (status: {response.status_code})")
        print()
        
    except Exception as e:
        print(f"   ❌ Cannot reach DeepAI: {e}")
        return
    
    try:
        # Test 2: API call with detailed logging
        print("Test 2: Calling text-generator API...")
        print(f"   Timeout: 60 seconds")
        
        headers = {
            'api-key': api_key,
            'User-Agent': 'KinD-FamilyDisplay/1.0'
        }
        
        data = {
            'text': prompt
        }
        
        # Add streaming if requested
        if use_stream:
            data['stream'] = 'true'
        
        print(f"   URL: https://api.deepai.org/api/text-generator")
        print(f"   Headers: {json.dumps({k: v if k != 'api-key' else v[:20]+'...' for k, v in headers.items()}, indent=6)}")
        print(f"   Data: {json.dumps(data, indent=6)}")
        print()
        
        if use_stream:
            print("   📡 Streaming response...")
            with httpx.stream(
                'POST',
                'https://api.deepai.org/api/text-generator',
                data=data,
                headers=headers,
                timeout=60.0
            ) as response:
                print(f"   Response status: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ Stream started, receiving data...")
                    print()
                    
                    full_text = ""
                    for line in response.iter_lines():
                        if line:
                            print(f"   📨 {line}")
                            full_text += line + "\n"
                    
                    print()
                    print(f"   ✅ Stream complete!")
                    print(f"   Full response length: {len(full_text)} bytes")
                    
                else:
                    print(f"   ❌ Stream failed with status {response.status_code}")
                    print(f"   Response: {response.text}")
        else:
            response = httpx.post(
                'https://api.deepai.org/api/text-generator',
                data=data,
                headers=headers,
                timeout=60.0
            )
            
            print(f"   Response status: {response.status_code}")
            print(f"   Response headers: {dict(response.headers)}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                print("   ✅ SUCCESS!")
                print(f"   Generated text: {result.get('output', 'N/A')}")
                print()
                print(f"   Full response: {json.dumps(result, indent=6)}")
                
            else:
                print(f"   ❌ API Error {response.status_code}")
                print(f"   Response body: {response.text}")
                print()
                
                # Try to parse error
                try:
                    error_json = response.json()
                    print(f"   Parsed error: {json.dumps(error_json, indent=6)}")
                except:
                    pass
                
    except httpx.TimeoutException as e:
        print(f"   ❌ Request timeout after 60 seconds: {e}")
        print()
        print("   💡 DeepAI is taking too long. Consider:")
        print("      1. Using the fallback templates (they're good!)")
        print("      2. Switching to Gemini Flash (free & fast)")
        print("      3. Trying the streaming API (--stream flag)")
        
    except httpx.RequestError as e:
        print(f"   ❌ Request failed: {e}")
        
    except Exception as e:
        print(f"   ❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        print()
        print("Full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_deepai.py YOUR_DEEPAI_API_KEY [--stream]")
        print()
        print("Options:")
        print("  --stream    Enable streaming mode to see responses as they generate")
        print()
        print("Get your API key from: https://deepai.org/dashboard/profile")
        sys.exit(1)
    
    api_key = sys.argv[1]
    use_stream = '--stream' in sys.argv
    
    test_deepai_sync(api_key, use_stream)
