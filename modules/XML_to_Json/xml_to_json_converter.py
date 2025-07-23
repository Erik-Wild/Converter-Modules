import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional


class XMLToJsonConverter:
    """Converts XML files to JSON format"""

    def __init__(self):
        self.preserve_attributes = True
        self.attribute_prefix = "@"
        self.text_key = "#text"
        self.list_tags = []  # Tags that should always be arrays

    def convert_file(self, xml_file_path: str, output_path: str = None) -> str:
        """
        Convert XML file to JSON

        Args:
            xml_file_path: Path to input XML file
            output_path: Path for output JSON file (optional)

        Returns:
            Path to generated JSON file
        """
        try:
            # Parse XML
            tree = ET.parse(xml_file_path)
            root = tree.getroot()

            # Convert to dictionary
            json_data = self.xml_to_dict(root)

            # Determine output path
            if not output_path:
                output_path = xml_file_path.rsplit('.', 1)[0] + '.json'

            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            return output_path

        except Exception as e:
            raise Exception(f"Error converting XML to JSON: {str(e)}")

    def xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}

        # Handle attributes
        if self.preserve_attributes and element.attrib:
            for key, value in element.attrib.items():
                result[f"{self.attribute_prefix}{key}"] = value

        # Handle text content
        if element.text and element.text.strip():
            if len(element) == 0:  # Leaf node with text
                if result:  # Has attributes
                    result[self.text_key] = element.text.strip()
                else:  # Just text
                    return element.text.strip()
            else:  # Has children and text
                result[self.text_key] = element.text.strip()

        # Handle child elements
        child_dict = {}
        for child in element:
            child_data = self.xml_to_dict(child)

            if child.tag in child_dict:
                # Convert to list if multiple children with same tag
                if not isinstance(child_dict[child.tag], list):
                    child_dict[child.tag] = [child_dict[child.tag]]
                child_dict[child.tag].append(child_data)
            else:
                # Force list for specified tags
                if child.tag in self.list_tags:
                    child_dict[child.tag] = [child_data]
                else:
                    child_dict[child.tag] = child_data

        result.update(child_dict)

        # If only one key and it's not an attribute or text, return the value directly
        if len(result) == 1 and not any(
                k.startswith(self.attribute_prefix) for k in result.keys()) and self.text_key not in result:
            return list(result.values())[0]

        return result

    def set_options(self, preserve_attributes: bool = True,
                    attribute_prefix: str = "@",
                    text_key: str = "#text",
                    list_tags: List[str] = None):
        """Configure conversion options"""
        self.preserve_attributes = preserve_attributes
        self.attribute_prefix = attribute_prefix
        self.text_key = text_key
        self.list_tags = list_tags or []


def convert(input_files: List[str], output_dir: str = None, additional_files: List[str] = None, **options) -> List[str]:
    """
    Main conversion function for the module system

    Args:
        :param input_files: List of XML file paths to convert
        :param output_dir: Directory for output files
        :param additional_files: List of additional files
        :param options: Conversion options

    Returns:
        List of generated JSON file paths

    """
    converter = XMLToJsonConverter()

    # Apply options
    if options:
        converter.set_options(
            preserve_attributes=options.get('preserve_attributes', True),
            attribute_prefix=options.get('attribute_prefix', '@'),
            text_key=options.get('text_key', '#text'),
            list_tags=options.get('list_tags', [])
        )

    output_files = []

    for input_file in input_files:
        try:
            if not input_file.lower().endswith(('.xml', '.pdi')):
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


if __name__ == "__main__":
    # Test the converter
    test_files = ["test.xml"]
    results = convert(test_files)
    print(f"Converted files: {results}")