"""Script to trigger analysis on a scraping job."""
import requests
import sys

# Configuration
BASE_URL = "http://localhost:8080"
JOB_ID = 3  # Change this to your job ID

def get_token():
    """Get token from user input."""
    print("=" * 60)
    print("ANALYSIS TRIGGER SCRIPT")
    print("=" * 60)
    token = input("\nEnter your authentication token (from browser localStorage): ").strip()
    return token

def trigger_analysis(job_id: int, token: str):
    """Trigger analysis for a scraping job."""
    url = f"{BASE_URL}/api/analysis/job/{job_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Default analysis configuration
    payload = {
        "extract_nouns": True,
        "extract_entities": True,
        "max_nouns": 100,
        "min_frequency": 2
    }

    print(f"\nTriggering analysis for scraping job {job_id}...")
    print(f"URL: {url}")

    try:
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 202:
            result = response.json()
            print("\n✓ Analysis queued successfully!")
            print(f"  Status: {result.get('status')}")
            print(f"  Message: {result.get('message')}")
            print("\nThe Celery worker will process the analysis in the background.")
            print("Check the logs for progress.")
            return True
        else:
            print(f"\n✗ Failed to queue analysis")
            print(f"  Status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

if __name__ == "__main__":
    # Check if job ID provided as argument
    if len(sys.argv) > 1:
        try:
            JOB_ID = int(sys.argv[1])
        except ValueError:
            print(f"Invalid job ID: {sys.argv[1]}")
            sys.exit(1)

    print("\nNOTE: Make sure the Celery worker is running!")
    print("      celery -A backend.celery_app worker -Q analysis --loglevel=info")

    token = get_token()

    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)

    success = trigger_analysis(JOB_ID, token)

    if success:
        print("\n" + "=" * 60)
        print("NEXT: Monitor the Celery worker logs to see progress")
        print("      After analysis completes, you can create networks!")
        print("=" * 60)
        sys.exit(0)
    else:
        sys.exit(1)
