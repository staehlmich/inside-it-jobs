import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os

class JobExtractor:
    """
    A tool to extract and format job listings from the ictjobs.ch RSS feed
    specifically for weekly newsletters.
    """

    def __init__(self, feed_url: str):
        """
        Initializes the JobExtractor with the target RSS feed URL.

        :param feed_url: The URL of the XML RSS feed.
        """
        self.feed_url = feed_url

    def get_latest_monday(self, current_date: datetime = None) -> datetime.date:
        """
        Calculates the date of the most recent Monday relative to the current date.

        :param current_date: The date to start from (defaults to now).
        :return: A date object representing the target Monday.
        """
        if current_date is None:
            current_date = datetime.now()
        # weekday(): Monday is 0, Sunday is 6
        days_to_subtract = current_date.weekday()
        latest_monday = current_date - timedelta(days=days_to_subtract)
        return latest_monday.date()

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

    def parse_jobs(self, xml_content: bytes, target_date: datetime.date) -> list[dict]:
        """
        Parses the XML and extracts the top 3 jobs for the target Monday.
        Falls back to the 3 latest jobs if no exact match is found.

        :param xml_content: The raw XML bytes.
        :param target_date: The Monday we are looking for.
        :return: A list of job dictionaries containing 'title' and 'link'.
        """
        root = ET.fromstring(xml_content)
        channel = root.find('channel')
        jobs = []

        # Strategy 1: Look for exact matches for the target Monday
        for item in channel.findall('item'):
            pub_date = self._parse_pub_date(item.find('pubDate').text)
            if pub_date == target_date:
                jobs.append({
                    'title': item.find('title').text,
                    'link': item.find('link').text
                })
                if len(jobs) >= 3:
                    return jobs

        # Strategy 2: Fallback to the 3 latest jobs published on or before the target date
        if not jobs:
            for item in channel.findall('item'):
                pub_date = self._parse_pub_date(item.find('pubDate').text)
                if pub_date <= target_date:
                    jobs.append({
                        'title': item.find('title').text,
                        'link': item.find('link').text
                    })
                    if len(jobs) >= 3:
                        break
        return jobs

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

    def run(self):
        """
        Main execution flow: fetch, parse, format, and output results.
        Supports both console output and GitHub Actions Job Summary.
        """
        current_date = datetime.now()
        target_monday = self.get_latest_monday(current_date)

        print(f"Current Date: {current_date.strftime('%Y-%m-%d')}")
        print(f"Target Monday: {target_monday}")

        try:
            xml_data = self.fetch_xml_content()
            jobs = self.parse_jobs(xml_data, target_monday)
            output = self.format_as_markdown(jobs)

            print("\nNewsletter Entries:")
            print(output)

            # Integration with GitHub Actions Summary
            if 'GITHUB_STEP_SUMMARY' in os.environ:
                self._write_github_summary(target_monday, output)

        except Exception as e:
            print(f"Error during execution: {e}")

    def _write_github_summary(self, date, content):
        """Writes the output to the GitHub Actions workflow summary."""
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(f"### 🚀 Weekly Jobs for {date}\n")
            f.write("Copy the entries below for your newsletter:\n\n")
            f.write(content + "\n\n")
            f.write("---\n*Generated by JobExtractor OOP Tool*")

if __name__ == "__main__":
    FEED_URL = "https://ictjobs.ch/custom-feed/inside-it/"
    extractor = JobExtractor(FEED_URL)
    extractor.run()
