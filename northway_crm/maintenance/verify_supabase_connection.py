from services.supabase_service import init_supabase
class MockApp:
    config = {
        'SUPABASE_URL': 'https://bnumpvhsfujpprovajkt.supabase.co',
        'SUPABASE_KEY': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJudW1wdmhzZnVqcHByb3Zhamt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgzNjA5OTgsImV4cCI6MjA4MzkzNjk5OH0.pVcON2srZ2FXQ36Q-72WAHB-gVdrP_5Se-_K8XQ15Gs'
    }

print("Initializing Supabase Client...")
supabase = init_supabase(MockApp())

if supabase:
    print("Supabase Client initialized successfully.")
    try:
        print("Attempting connection test (sign in with invalid user)...")
        res = supabase.auth.sign_in_with_password({"email": "fake@email.com", "password": "fake"})
    except Exception as e:
        print(f"Connection made (expected error for invalid user): {e}")
        # If we got a response from the server (even 400), it means connection is good.
else:
    print("Failed to initialize Supabase Client.")
