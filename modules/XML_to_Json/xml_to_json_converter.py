import json
import re
from typing import List, Dict, Any

class PDIToJsonConverter:
    """Converts PDI files to JSON format"""

    def __init__(self):
        pass  # No specific options needed for now

    def convert_file(self, pdi_file_path: str, output_path: str = None) -> str:
        """
        Convert PDI file to JSON

        Args:
            pdi_file_path: Path to input PDI file
            output_path: Path for output JSON file (optional)

        Returns:
            Path to generated JSON file
        """
        try:
            # Read PDI content
            with open(pdi_file_path, 'r', encoding='utf-8') as f:
                input_text = f.read()

            # Parse to data
            json_data = self.parse_pdi(input_text)

            # Determine output path
            if not output_path:
                output_path = pdi_file_path.rsplit('.', 1)[0] + '.json'

            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)

            return output_path

        except Exception as e:
            raise Exception(f"Error converting PDI to JSON: {str(e)}")

    def parse_pdi(self, text: str) -> List[Dict[str, Any]]:
        """Parse PDI text to list of documents"""
        documents = []
        # Split the text into lines
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('<DOCUMENT filename='):
                # Extract filename
                match = re.search(r'<DOCUMENT filename="([^"]+)"', line)
                if match:
                    filename = match.group(1)
                else:
                    i += 1
                    continue
                content_lines = []
                i += 1
                # Collect lines until </DOCUMENT>
                while i < len(lines) and not lines[i].strip().startswith('</DOCUMENT>'):
                    content_lines.append(lines[i])
                    i += 1
                # Parse the content lines into entries
                entries = []
                j = 0
                while j < len(content_lines):
                    cl = content_lines[j].strip()
                    if cl.startswith('PA'):
                        # Extract type and id
                        parts = cl.split('::', 1)
                        entry_type = parts[0]
                        entry_id = parts[1] if len(parts) > 1 else ''
                        params = []
                        j += 1
                        # Collect subsequent params until next PA or end
                        while j < len(content_lines) and not content_lines[j].strip().startswith('PA'):
                            param = content_lines[j].strip()
                            if param:  # Skip empty params
                                params.append(param)
                            j += 1
                        entries.append({
                            'type': entry_type,
                            'id': entry_id,
                            'params': params
                        })
                    else:
                        j += 1
                documents.append({
                    'filename': filename,
                    'entries': entries
                })
            else:
                i += 1
        return documents

def convert(input_files: List[str], output_dir: str = None, **options) -> List[str]:
    """
    Main conversion function for the module system

    Args:
        input_files: List of PDI file paths to convert
        output_dir: Directory for output files
        **options: Conversion options (currently none)

    Returns:
        List of generated JSON file paths
    """
    converter = PDIToJsonConverter()

    # No options to set for now

    output_files = []

    for input_file in input_files:
        try:
            if not input_file.lower().endswith('.pdi'):
                continue

            if output_dir:
                import os
                filename = os.path.basename(input_file).rsplit('.', 1)[0] + '.json'
                output_path = os.path.join(output_dir, filename)
            else:
                output_path = None

            result_path = converter.convert_file(input_file, output_path)
            output_files.append(result_path)

        except Exception as e:
            print(f"Error converting {input_file}: {str(e)}")

    return output_files