"""Seed script: print the path to demo_requests.txt (no DB changes, data already committed)."""
import os

demo_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "demo", "demo_requests.txt")
if os.path.exists(demo_file):
    print(f"demo_requests.txt exists at: {demo_file}")
else:
    print(f"ERROR: {demo_file} not found")
