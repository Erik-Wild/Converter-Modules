import json
import re
import os
import argparse
from typing import List, Dict, Any

class PDIToJsonConverter:
    """Converts PDI files to JSON format"""

    def __init__(self):
        pass

    def convert_file(self, pdi_file_path: str, output_path: str = None) -> str:
        """
        Convert PDI file to JSON
        """
        try:
            # Read PDI content safely
            with open(pdi_file_path, 'r', encoding='utf-8', errors='replace') as f:
                input_text = f.read()

            # Parse PDI content
            json_data = self.parse_pdi(input_text)

            # Determine output path
            if not output_path:
                output_path = pdi_file_path.rsplit('.', 1)[0] + '.json'

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)

            print(f"[OK] Converted {pdi_file_path} -> {output_path}")
            return output_path

        except Exception as e:
            raise Exception(f"Error converting {pdi_file_path}: {str(e)}")

    def parse_pdi(self, text: str) -> List[Dict[str, Any]]:
        """Parse PDI text to list of documents"""
        documents = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('<DOCUMENT'):
                # Extract filename using flexible regex
                match = re.search(r'<DOCUMENT\s+[^>]*filename="([^"]+)"', line, re.IGNORECASE)
                if not match:
                    i += 1
                    continue

                filename = match.group(1)
                content_lines = []
                i += 1

                # Collect lines until </DOCUMENT>
                while i < len(lines) and not lines[i].strip().startswith('</DOCUMENT>'):
                    content_lines.append(lines[i])
                    i += 1

                # Skip </DOCUMENT> if present
                if i < len(lines) and lines[i].strip().startswith('</DOCUMENT>'):
                    i += 1

                # Parse entries inside the document
                entries = self._parse_entries(content_lines)

                documents.append({
                    'filename': filename,
                    'entries': entries
                })
            else:
                i += 1

        return documents

    def _parse_entries(self, content_lines: List[str]) -> List[Dict[str, Any]]:
        """Parse PA entries inside a document"""
        entries = []
        j = 0
        while j < len(content_lines):
            cl = content_lines[j].strip()
            if cl.startswith('PA'):
                parts = cl.split('::', 1)
                entry_type = parts[0].strip()
                entry_id = parts[1].strip() if len(parts) > 1 else None
                params = []
                j += 1
                # Collect parameters until next PA or end
                while j < len(content_lines) and not content_lines[j].strip().startswith('PA'):
                    param = content_lines[j].strip()
                    if param:
                        params.append(param)
                    j += 1
                entries.append({
                    'type': entry_type,
                    'id': entry_id,
                    'params': params
                })
            else:
                j += 1
        return entries


def convert(input_files: List[str], output_dir: str = None) -> List[str]:
    """Convert multiple PDI files to JSON"""
    converter = PDIToJsonConverter()
    output_files = []

    for input_file in input_files:
        if not input_file.lower().endswith('.pdi'):
            print(f"[SKIP] {input_file} is not a .pdi file")
            continue

        if output_dir:
            filename = os.path.basename(input_file).rsplit('.', 1)[0] + '.json'
            output_path = os.path.join(output_dir, filename)
        else:
            output_path = None

        try:
            result_path = converter.convert_file(input_file, output_path)
            output_files.append(result_path)
        except Exception as e:
            print(f"[ERROR] {str(e)}")

    return output_files
