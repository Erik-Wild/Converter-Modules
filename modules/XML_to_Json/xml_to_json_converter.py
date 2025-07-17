import json
import os
import argparse
from typing import List
import xmltodict

class PDIToJsonConverter:
    """Converts XML-based PDI files to JSON format"""

    def __init__(self):
        pass

    def convert_file(self, pdi_file_path: str, output_path: str = None) -> str:
        """
        Convert a PDI (XML) file to JSON
        """
        try:
            # Read XML content
            with open(pdi_file_path, 'r', encoding='utf-8', errors='replace') as f:
                xml_text = f.read()

            # Parse XML into dictionary
            json_data = xmltodict.parse(xml_text)

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

