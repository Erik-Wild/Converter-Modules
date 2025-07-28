import json
import xml.etree.ElementTree as ET
import re
import os
from typing import Dict, Any, List, Optional


class XMLToJsonConverter:
    """Converts XML files to JSON format"""

    def __init__(self):
        self.preserve_attributes = True
        self.attribute_prefix = "@"
        self.text_key = "#text"
        self.list_tags = []  # Tags that should always be arrays
        self.debug_mode = True  # Enable detailed debugging

    def preprocess_xml(self, xml_content: str) -> str:
        """
        Preprocess XML content to fix common issues that might cause parsing errors

        Args:
            xml_content: Raw XML content

        Returns:
            Preprocessed XML content
        """
        if self.debug_mode:
            print(f"Preprocessing XML content of length {len(xml_content)}")

        # Fix malformed XML declaration - critical to handle first
        xml_decl_pattern = r'<\?xml\s+version\s*=\s*"([^"]*)\??>'
        if re.search(xml_decl_pattern, xml_content):
            if self.debug_mode:
                print("Found malformed XML declaration, fixing...")

            # Fix missing closing quote in XML declaration
            xml_content = re.sub(r'<\?xml\s+version\s*=\s*"([^"]*)\?>',
                               r'<?xml version="\1"?>',
                               xml_content)

            # Fix other common XML declaration issues
            xml_content = re.sub(r'<\?xml\s+version\s*=\s*"([^"]*)>',
                               r'<?xml version="\1"?>',
                               xml_content)

        # Add proper XML declaration if missing
        if not xml_content.strip().startswith('<?xml'):
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content

        # Fix unescaped quotes in attribute values
        # This is a common issue in PDI files
        processed_content = xml_content

        # First pass: simple attribute with unescaped quotes
        pattern = r'=\s*"([^"]*)"([^"]*)"([^"]*)"'
        while re.search(pattern, processed_content):
            if self.debug_mode:
                print("Found unescaped quotes in attributes, fixing...")

            def replace_quotes(match):
                # Replace unescaped quotes with &quot;
                content = match.group(1) + match.group(2) + match.group(3)
                content = content.replace('"', '&quot;')
                return f'="{content}"'

            processed_content = re.sub(pattern, replace_quotes, processed_content)

        # More aggressive fixing for attributes that might span multiple lines
        pattern = r'=\s*"([^>]*?)"([^>]*?)"([^>]*?)"'
        while re.search(pattern, processed_content):
            if self.debug_mode:
                print("Found complex unescaped quotes, fixing...")
            processed_content = re.sub(pattern, replace_quotes, processed_content)

        # Fix standalone ampersands not part of entities
        processed_content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', processed_content)

        # Fix unclosed CDATA sections
        if '<![CDATA[' in processed_content and ']]>' not in processed_content:
            if self.debug_mode:
                print("Found unclosed CDATA section, fixing...")
            processed_content = processed_content.replace('<![CDATA[', '')

        # Fix other special cases in PDI files
        processed_content = processed_content.replace('\\', '\\\\')  # Escape backslashes

        # Remove control characters that might cause XML parsing issues
        processed_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', processed_content)

        # Handle malformed attributes (no quotes around values)
        # Fix the syntax error in the regex replacement
        processed_content = re.sub(r'=([^\s">]+)(\s|>)', r'"\1"\2', processed_content)

        # Fix missing closing tags - only for basic elements
        for tag_match in re.finditer(r'<([a-zA-Z0-9_:-]+)([^>]*)>', processed_content):
            tag_name = tag_match.group(1)
            # Check if self-closing or has a closing tag
            if not re.search(f'</{tag_name}>', processed_content) and not '/' in tag_match.group(2):
                processed_content += f'</{tag_name}>'
                if self.debug_mode:
                    print(f"Added missing closing tag for <{tag_name}>")

        return processed_content

    def convert_file(self, xml_file_path: str, output_path: str = None) -> str:
        """
        Convert XML file to JSON

        Args:
            xml_file_path: Path to input XML file
            output_path: Path for output JSON file (optional)

        Returns:
            Path to generated JSON file
        """
        if self.debug_mode:
            print(f"Converting file: {xml_file_path}")

        try:
            # Try reading as text first
            try:
                with open(xml_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    xml_content = f.read()

                # Check if it looks like XML
                if not (xml_content.strip().startswith('<?xml') or xml_content.strip().startswith('<')):
                    raise ValueError("File does not appear to be XML, trying binary mode")

                # Preprocess XML content to fix common issues
                processed_xml = self.preprocess_xml(xml_content)

            except UnicodeDecodeError:
                # If it fails as text, try binary mode for PDI files
                if self.debug_mode:
                    print("UnicodeDecodeError: Trying binary mode")
                try:
                    with open(xml_file_path, 'rb') as f:
                        binary_content = f.read()
                    # Try to decode with different encodings
                    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            xml_content = binary_content.decode(encoding, errors='replace')
                            if self.debug_mode:
                                print(f"Successfully decoded with {encoding}")
                            break
                        except UnicodeDecodeError:
                            continue

                    processed_xml = self.preprocess_xml(xml_content)
                except Exception as bin_err:
                    raise Exception(f"Failed to read file in binary mode: {bin_err}")

            # Try multiple parsing methods
            root = None
            errors = []

            # Method 1: Standard ElementTree
            try:
                root = ET.fromstring(processed_xml)
                if self.debug_mode:
                    print("Successfully parsed with standard ElementTree")
            except ET.ParseError as e:
                errors.append(f"Standard XML parsing failed: {e}")

                # Method 2: Try with lxml which is more lenient
                try:
                    import lxml.etree as lxml_ET
                    parser = lxml_ET.XMLParser(recover=True)
                    root = lxml_ET.fromstring(processed_xml.encode('utf-8'), parser)
                    if self.debug_mode:
                        print("Successfully parsed XML using lxml with recovery mode")
                    # Convert lxml Element to ElementTree Element
                    root_str = lxml_ET.tostring(root, encoding='utf-8').decode('utf-8')
                    root = ET.fromstring(root_str)
                except ImportError:
                    errors.append("lxml not available")

                    # Method 3: Try with XMLBuilder
                    try:
                        from xml.sax.saxutils import escape

                        # Escape special characters in XML
                        safe_xml = escape(processed_xml)

                        # Try again with escaped content
                        root = ET.fromstring(safe_xml)
                        if self.debug_mode:
                            print("Successfully parsed with escaped XML")
                    except Exception as builder_err:
                        errors.append(f"XMLBuilder failed: {builder_err}")

                        # Method 4: Try reading directly with minidom
                        try:
                            from xml.dom import minidom
                            dom = minidom.parseString(processed_xml)
                            # Convert DOM to ElementTree
                            xml_str = dom.toxml()
                            root = ET.fromstring(xml_str)
                            if self.debug_mode:
                                print("Successfully parsed with minidom")
                        except Exception as dom_err:
                            errors.append(f"minidom failed: {dom_err}")
                except Exception as lxml_err:
                    errors.append(f"lxml failed: {lxml_err}")

            if not root:
                # Last resort: try to fix the specific error by examining the error message
                for error in errors:
                    if "line" in error and "column" in error:
                        # Extract line and column information
                        line_match = re.search(r'line (\d+)', error)
                        col_match = re.search(r'column (\d+)', error)

                        if line_match and col_match:
                            line_num = int(line_match.group(1))
                            col_num = int(col_match.group(1))

                            # Get the problematic line
                            lines = processed_xml.split('\n')
                            if line_num <= len(lines):
                                problem_line = lines[line_num - 1]
                                if self.debug_mode:
                                    print(f"Problematic line ({line_num}): {problem_line}")

                                # Try to fix the specific character
                                if col_num <= len(problem_line):
                                    problem_char = problem_line[col_num - 1]
                                    if self.debug_mode:
                                        print(f"Problematic character at column {col_num}: '{problem_char}'")

                                    # Replace the problematic character
                                    if '"' in problem_line and problem_line.count('"') % 2 == 1:
                                        # Fix missing quotes
                                        fixed_line = problem_line + '"'
                                    else:
                                        # Replace with space as fallback
                                        fixed_line = problem_line[:col_num-1] + ' ' + problem_line[col_num:]

                                    lines[line_num - 1] = fixed_line

                                    fixed_xml = '\n'.join(lines)
                                    try:
                                        root = ET.fromstring(fixed_xml)
                                        if self.debug_mode:
                                            print("Successfully parsed after fixing specific character!")
                                    except Exception as fix_err:
                                        errors.append(f"Character fixing failed: {fix_err}")

                # If all else fails, try to convert using xmltodict as a last resort
                if not root:
                    try:
                        import xmltodict
                        # Parse XML into dict using xmltodict (more tolerant)
                        xml_dict = xmltodict.parse(processed_xml)

                        # Convert back to XML string and then to ElementTree
                        xml_str = xmltodict.unparse(xml_dict)
                        root = ET.fromstring(xml_str)
                        if self.debug_mode:
                            print("Successfully parsed using xmltodict workaround")
                    except Exception as xmltodict_err:
                        errors.append(f"xmltodict method failed: {xmltodict_err}")

                if not root:
                    raise Exception(f"Failed to parse XML with multiple methods. Errors: {', '.join(errors)}")

            # Convert to dictionary
            json_data = self.xml_to_dict(root)

            # Determine output path
            if not output_path:
                output_path = xml_file_path.rsplit('.', 1)[0] + '.json'

            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            if self.debug_mode:
                print(f"Successfully converted to: {output_path}")
            return output_path

        except Exception as e:
            if self.debug_mode:
                import traceback
                traceback.print_exc()
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
                    list_tags: List[str] = None,
                    debug_mode: bool = False):
        """Configure conversion options"""
        self.preserve_attributes = preserve_attributes
        self.attribute_prefix = attribute_prefix
        self.text_key = text_key
        self.list_tags = list_tags or []
        self.debug_mode = debug_mode


def convert(input_files: List[str], output_dir: str = None, additional_files: List[str] = None, **options) -> List[str]:
    """
    Main conversion function for the module system

    Args:
        input_files: List of XML file paths to convert
        output_dir: Directory for output files
        additional_files: List of additional files
        options: Conversion options

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
            list_tags=options.get('list_tags', []),
            debug_mode=options.get('debug_mode', True)  # Enable debug by default
        )

    output_files = []

    for input_file in input_files:
        try:
            if not input_file.lower().endswith(('.xml', '.pdi')):
                print(f"Skipping {input_file} - not an XML or PDI file")
                continue

            if output_dir:
                filename = os.path.basename(input_file).rsplit('.', 1)[0] + '.json'
                output_path = os.path.join(output_dir, filename)
            else:
                output_path = None

            print(f"Processing {input_file}...")
            result_path = converter.convert_file(input_file, output_path)
            output_files.append(result_path)
            print(f"Successfully converted to {result_path}")

        except Exception as e:
            print(f"Error converting {input_file}: {str(e)}")

    return output_files


if __name__ == "__main__":
    # Test the converter
    test_files = ["test.xml"]
    results = convert(test_files)
    print(f"Converted files: {results}")
