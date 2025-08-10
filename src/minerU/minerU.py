import os
import requests
import time
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Union, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MinerUClient:
    """Client for MinerU API to parse papers and extract markdown content."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize MinerU client.

        Args:
            api_key: MinerU API key. If not provided, will try to get from MINERU_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("MINERU_API_KEY")
        if not self.api_key:
            raise ValueError("MINERU_API_KEY not found in environment variables")

        self.base_url = "https://mineru.net/api/v4"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def parse_from_url(self, url: str, output_dir: str = ".", **kwargs) -> str:
        """
        Parse a paper from URL and save markdown output.

        Args:
            url: URL of the paper to parse
            output_dir: Directory to save the output markdown file
            **kwargs: Additional parameters for parsing (is_ocr, enable_formula, etc.)

        Returns:
            Path to the output markdown file
        """
        logger.info(f"Starting to parse paper from URL: {url}")

        # Create parsing task
        task_id = self._create_parsing_task(url, **kwargs)
        logger.info(f"Created parsing task with ID: {task_id}")

        # Wait for task completion
        result = self._wait_for_task_completion(task_id)

        if result["state"] != "done":
            raise Exception(f"Parsing failed: {result.get('err_msg', 'Unknown error')}")

        # Download and extract results
        markdown_file = self._download_and_extract_results(
            result["full_zip_url"], output_dir
        )
        logger.info(f"Successfully parsed paper. Output saved to: {markdown_file}")

        return markdown_file

    def parse_from_file(self, file_path: str, output_dir: str = ".", **kwargs) -> str:
        """
        Parse a local PDF file and save markdown output.

        Args:
            file_path: Path to the local PDF file
            output_dir: Directory to save the output markdown file
            **kwargs: Additional parameters for parsing

        Returns:
            Path to the output markdown file
        """
        logger.info(f"Starting to parse local file: {file_path}")

        # Get upload URLs
        batch_id, upload_urls = self._get_upload_urls([file_path], **kwargs)
        logger.info(f"Got upload URLs for batch ID: {batch_id}")

        # Upload file
        self._upload_file(file_path, upload_urls[0])
        logger.info("File uploaded successfully")

        # Wait for parsing completion
        result = self._wait_for_batch_completion(batch_id, Path(file_path).name)

        if result["state"] != "done":
            raise Exception(f"Parsing failed: {result.get('err_msg', 'Unknown error')}")

        # Download and extract results
        markdown_file = self._download_and_extract_results(
            result["full_zip_url"], output_dir
        )
        logger.info(f"Successfully parsed file. Output saved to: {markdown_file}")

        return markdown_file

    def _create_parsing_task(self, url: str, **kwargs) -> str:
        """Create a parsing task for a URL."""
        url = f"{self.base_url}/extract/task"

        data = {
            "url": url,
            "is_ocr": kwargs.get("is_ocr", True),
            "enable_formula": kwargs.get("enable_formula", True),
            "enable_table": kwargs.get("enable_table", True),
            "language": kwargs.get("language", "auto"),
            "model_version": kwargs.get("model_version", "v2"),
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

        result = response.json()
        if result["code"] != 0:
            raise Exception(f"Failed to create parsing task: {result['msg']}")

        return result["data"]["task_id"]

    def _get_upload_urls(self, file_paths: list, **kwargs) -> tuple:
        """Get upload URLs for local files."""
        url = f"{self.base_url}/file-urls/batch"

        files = []
        for file_path in file_paths:
            files.append(
                {
                    "name": Path(file_path).name,
                    "is_ocr": kwargs.get("is_ocr", True),
                    "data_id": kwargs.get("data_id", Path(file_path).stem),
                }
            )

        data = {
            "enable_formula": kwargs.get("enable_formula", True),
            "enable_table": kwargs.get("enable_table", True),
            "language": kwargs.get("language", "auto"),
            "model_version": kwargs.get("model_version", "v2"),
            "files": files,
        }

        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()

        result = response.json()
        if result["code"] != 0:
            raise Exception(f"Failed to get upload URLs: {result['msg']}")

        return result["data"]["batch_id"], result["data"]["file_urls"]

    def _upload_file(self, file_path: str, upload_url: str):
        """Upload a file to the provided upload URL."""
        with open(file_path, "rb") as f:
            response = requests.put(upload_url, data=f)
            response.raise_for_status()

    def _wait_for_task_completion(
        self, task_id: str, max_wait_time: int = 3600
    ) -> Dict[str, Any]:
        """Wait for a single task to complete."""
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            result = self._get_task_status(task_id)

            if result["state"] == "done":
                return result
            elif result["state"] == "failed":
                raise Exception(
                    f"Task failed: {result.get('err_msg', 'Unknown error')}"
                )

            logger.info(f"Task {task_id} status: {result['state']}")
            if result["state"] == "running" and "extract_progress" in result:
                progress = result["extract_progress"]
                logger.info(
                    f"Progress: {progress['extracted_pages']}/{progress['total_pages']} pages"
                )

            time.sleep(10)  # Wait 10 seconds before checking again

        raise TimeoutError(
            f"Task {task_id} did not complete within {max_wait_time} seconds"
        )

    def _wait_for_batch_completion(
        self, batch_id: str, file_name: str, max_wait_time: int = 3600
    ) -> Dict[str, Any]:
        """Wait for a batch task to complete."""
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            result = self._get_batch_status(batch_id)

            # Find the specific file result
            for file_result in result["extract_result"]:
                if file_result["file_name"] == file_name:
                    if file_result["state"] == "done":
                        return file_result
                    elif file_result["state"] == "failed":
                        raise Exception(
                            f"Task failed: {file_result.get('err_msg', 'Unknown error')}"
                        )

                    logger.info(f"File {file_name} status: {file_result['state']}")
                    if (
                        file_result["state"] == "running"
                        and "extract_progress" in file_result
                    ):
                        progress = file_result["extract_progress"]
                        logger.info(
                            f"Progress: {progress['extracted_pages']}/{progress['total_pages']} pages"
                        )
                    break

            time.sleep(10)  # Wait 10 seconds before checking again

        raise TimeoutError(
            f"Batch task {batch_id} did not complete within {max_wait_time} seconds"
        )

    def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a single task."""
        url = f"{self.base_url}/extract/task/{task_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        result = response.json()
        if result["code"] != 0:
            raise Exception(f"Failed to get task status: {result['msg']}")

        return result["data"]

    def _get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get the status of a batch task."""
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        result = response.json()
        if result["code"] != 0:
            raise Exception(f"Failed to get batch status: {result['msg']}")

        return result["data"]

    def _download_and_extract_results(self, zip_url: str, output_dir: str) -> str:
        """Download and extract the results ZIP file."""
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Download ZIP file
        logger.info("Downloading results...")
        response = requests.get(zip_url, stream=True)
        response.raise_for_status()

        # Save ZIP file temporarily
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
            for chunk in response.iter_content(chunk_size=8192):
                temp_zip.write(chunk)
            temp_zip_path = temp_zip.name

        try:
            # Extract ZIP file
            logger.info("Extracting results...")
            with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
                zip_ref.extractall(output_dir)

            # Find markdown file
            markdown_files = list(Path(output_dir).glob("*.md"))
            if not markdown_files:
                raise FileNotFoundError("No markdown file found in extracted results")

            # Return the first markdown file found
            return str(markdown_files[0])

        finally:
            # Clean up temporary ZIP file
            os.unlink(temp_zip_path)


def main():
    """Main function to demonstrate usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse papers using MinerU API")
    parser.add_argument("input", help="URL or path to PDF file")
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--is-ocr", action="store_true", default=True, help="Enable OCR (default: True)"
    )
    parser.add_argument(
        "--enable-formula",
        action="store_true",
        default=True,
        help="Enable formula recognition (default: True)",
    )
    parser.add_argument(
        "--enable-table",
        action="store_true",
        default=True,
        help="Enable table recognition (default: True)",
    )
    parser.add_argument(
        "--language", default="auto", help="Document language (default: auto)"
    )
    parser.add_argument(
        "--model-version",
        default="v2",
        choices=["v1", "v2"],
        help="Model version (default: v2)",
    )

    args = parser.parse_args()

    try:
        client = MinerUClient()

        # Check if input is URL or file path
        if args.input.startswith(("http://", "https://")):
            output_file = client.parse_from_url(
                args.input,
                output_dir=args.output,
                is_ocr=args.is_ocr,
                enable_formula=args.enable_formula,
                enable_table=args.enable_table,
                language=args.language,
                model_version=args.model_version,
            )
        else:
            # Check if file exists
            if not os.path.exists(args.input):
                print(f"Error: File {args.input} does not exist")
                return 1

            output_file = client.parse_from_file(
                args.input,
                output_dir=args.output,
                is_ocr=args.is_ocr,
                enable_formula=args.enable_formula,
                enable_table=args.enable_table,
                language=args.language,
                model_version=args.model_version,
            )

        print(f"Successfully parsed paper. Output saved to: {output_file}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
