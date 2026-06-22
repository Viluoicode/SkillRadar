"""M0 spike — prove we can pull real data from a public ATS feed.

Run:  uv run python m0_spike.py   (or: python m0_spike.py)

If you see real job titles printed, M0 is done: you're holding real data and the
rest of the pipeline is just shaping it through the Medallion layers.
"""

import httpx

COMPANY = "stripe"  # any company that uses Greenhouse (board slug)
URL = f"https://boards-api.greenhouse.io/v1/boards/{COMPANY}/jobs"


def main() -> None:
    resp = httpx.get(URL, timeout=20)
    resp.raise_for_status()
    jobs = resp.json()["jobs"]

    print(f"Found {len(jobs)} jobs at {COMPANY}\n")
    for job in jobs[:5]:
        location = (job.get("location") or {}).get("name", "n/a")
        print("-", job["title"], "|", location)


if __name__ == "__main__":
    main()
