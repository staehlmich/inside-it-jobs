import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

class JobExtractor:
    """
    A tool to extract and format job listings from the ictjobs.ch feed
    specifically for weekly newsletters.
    """

    def __init__(self, feed_url: str):
        """
        Initializes the JobExtractor with the target RSS feed URL.

        :param feed_url: The URL of the XML RSS feed.
        """
        self.feed_url = feed_url

    def get_target_monday(self, current_date: datetime = None) -> datetime.date:
        """
        Calculates the target Monday for the newsletter.
        If today is Thursday or later, targets the NEXT Monday.
        Otherwise, targets the most recent Monday.

        :param current_date: The date to start from (defaults to now).
        :return: A date object representing the target Monday.
        """
        if current_date is None:
            current_date = datetime.now()
        
        weekday = current_date.weekday()
        if weekday >= 3:  # Thursday (3), Friday (4), etc.
            # Target the upcoming Monday
            days_to_add = (7 - weekday) % 7
            target_monday = current_date + timedelta(days=days_to_add)
        else:
            # Target the latest Monday
            days_to_subtract = weekday
            target_monday = current_date - timedelta(days=days_to_subtract)
            
        return target_monday.date()

    def fetch_xml_content(self) -> bytes:
        """
        Downloads the XML content from the configured feed URL.

        :return: The raw bytes of the XML response.
        :raises RequestException: If the network request fails.
        """
        response = requests.get(self.feed_url)
        response.raise_for_status()
        return response.content

    def _parse_pub_date(self, date_str: str) -> datetime.date:
        """
        Internal helper to parse various RSS date string formats.

        :param date_str: The raw date string from the XML.
        :return: A date object.
        """
        try:
            # Try full format with timezone: "Tue, 28 Apr 2026 09:07:00 +0000"
            return datetime.strptime(date_str[:25].strip(), '%a, %d %b %Y %H:%M:%S').date()
        except ValueError:
            # Fallback to simple date: "Tue, 28 Apr 2026"
            return datetime.strptime(date_str[:16], '%a, %d %b %Y').date()

    def parse_jobs(self, xml_content: bytes, target_date: datetime.date) -> tuple[list[dict], bool]:
        """
        Parses the XML and extracts the top 3 jobs for the target Monday.
        Falls back to the 3 latest jobs if no exact match is found.

        :param xml_content: The raw XML bytes.
        :param target_date: The Monday we are looking for.
        :return: A tuple of (list of job dictionaries, bool indicating if exact matches were found).
        """
        root = ET.fromstring(xml_content)
        # Define namespaces
        namespaces = {'job': 'https://ictjobs.ch'}
        channel = root.find('channel')
        jobs = []

        # Strategy 1: Look for exact matches for the target Monday in <job:premium>
        # Format is YYMMDD (e.g., 260504)
        target_str = target_date.strftime('%y%m%d')

        for item in channel.findall('item'):
            premium_elem = item.find('job:premium', namespaces)
            if premium_elem is not None and premium_elem.text:
                job_date_str = premium_elem.text.strip()
                if job_date_str == target_str:
                    jobs.append({
                        'title': item.find('title').text,
                        'link': item.find('link').text
                    })
                    if len(jobs) >= 3:
                        return jobs, True

        # If we found some but less than 3, we still count them as exact matches
        exact_matches_found = len(jobs) > 0

        # Strategy 2: Fallback to the 3 latest jobs published on or before the target date
        if not jobs:
            for item in channel.findall('item'):
                premium_elem = item.find('job:premium', namespaces)
                if premium_elem is not None and premium_elem.text:
                    try:
                        job_date_str = premium_elem.text.strip()
                        job_date = datetime.strptime(job_date_str, '%y%m%d').date()
                        if job_date <= target_date:
                            jobs.append({
                                'title': item.find('title').text,
                                'link': item.find('link').text
                            })
                            if len(jobs) >= 3:
                                break
                    except (ValueError, TypeError):
                        continue
        return jobs, exact_matches_found

    def format_as_markdown(self, jobs: list[dict]) -> str:
        """
        Formats the list of jobs into a markdown bulleted list.

        :param jobs: List of job dictionaries.
        :return: A formatted string ready for the newsletter.
        """
        if not jobs:
            return "No jobs found for the specified period."

        lines = [f"* **[{job['title']}]({job['link']})**" for job in jobs]
        return "\n".join(lines)

    def run(self, target_monday: datetime.date = None):
        """
        Main execution flow: fetch, parse, format, and output results.
        Supports both console output and GitHub Actions Job Summary.

        :param target_monday: Optional specific Monday to target (for testing).
        """
        current_date = datetime.now()
        if target_monday is None:
            target_monday = self.get_target_monday(current_date)

        print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
        print(f"Target Monday: {target_monday}")

        try:
            xml_data = self.fetch_xml_content()
            jobs, exact_match = self.parse_jobs(xml_data, target_monday)
            
            warning_msg = ""
            if not exact_match:
                warning_msg = f"No jobs for {target_monday} available yet."
                print(f"[Warning] {warning_msg} Showing latest available jobs instead.")

            output = self.format_as_markdown(jobs)

            print("\nNewsletter Entries:")
            print(output)

            # Integration with GitHub Actions Summary
            if 'GITHUB_STEP_SUMMARY' in os.environ:
                self._write_github_summary(current_date.date(), target_monday, output, warning_msg)
            
            # Always update README.md for a nice landing page
            self._write_readme(current_date.date(), target_monday, output, warning_msg)

        except Exception as e:
            print(f"Error during execution: {e}")

    def _write_github_summary(self, current_date, target_date, content, warning=""):
        """Writes the output to the GitHub Actions workflow summary."""
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(f"### 🗓️ Today is: {current_date}\n")
            f.write(f"### 🚀 Weekly Jobs for {target_date}\n")
            
            if warning:
                f.write(f"> {warning}\n")
                
            f.write("Copy the entries below for your newsletter:\n\n")
            f.write(content + "\n\n")
            f.write("---\n*Generated by JobExtractor OOP Tool*")

    def _write_readme(self, current_date, target_date, content, warning=""):
        """Writes the output to README.md for easy access."""
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(f"# 📋 Newsletter: Weekly Job Extraction\n\n")
            f.write(f"This page is automatically updated with the latest job listings for the newsletter.\n\n")
            f.write(f"**Schedule:** Runs every Thursday and Friday at 15:15, 15:30, 15:45, and 16:00 UTC.\n\n")
            f.write(f"### 🗓️ Extraction Date: {current_date}\n")
            f.write(f"### 🚀 Targeted Newsletter Week: {target_date}\n\n")
            
            if warning:
                f.write(f"> ⚠️ **Note:** {warning}\n\n")
                
            f.write("#### Newsletter Entries (Copy-Paste):\n\n")
            f.write("```markdown\n")
            f.write(content + "\n")
            f.write("```\n\n")
            f.write("---\n")
            f.write(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*")

if __name__ == "__main__":
    FEED_URL = "https://ictjobs.ch/custom-feed/inside-it/"
    extractor = JobExtractor(FEED_URL)
    extractor.run()
