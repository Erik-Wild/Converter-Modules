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
            print(f"First 100 characters: {xml_content[:100].replace(chr(10), '\\n')}")

            # Detailed debug for XML declaration
            xml_decl = xml_content.split('\n')[0] if '\n' in xml_content else xml_content[:50]
            print(f"XML declaration: '{xml_decl}'")
            print(f"Character by character analysis of XML declaration:")
            for i, char in enumerate(xml_decl):
                print(f"  Position {i}: '{char}' (ASCII: {ord(char)})")

        # CRITICAL FIX: Ensure the XML content is properly formed by extracting and
        # reconstructing the XML declaration from scratch
        if xml_content.startswith('<?xml'):
            # Find where the XML declaration ends
            decl_end = xml_content.find('?>')
            if decl_end > 0:
                # Extract the XML declaration
                declaration = xml_content[:decl_end + 2]

                # Extract version if present
                version_match = re.search(r'version\s*=\s*"([^"]*)"', declaration)
                version = version_match.group(1) if version_match else "1.0"

                # Extract encoding if present
                encoding_match = re.search(r'encoding\s*=\s*"([^"]*)"', declaration)
                encoding = encoding_match.group(1) if encoding_match else "UTF-8"

                # Rebuild a clean XML declaration
                clean_declaration = f'<?xml version="{version}" encoding="{encoding}"?>'

                if self.debug_mode:
                    print(f"Original declaration: '{declaration}'")
                    print(f"Cleaned declaration: '{clean_declaration}'")

                # Replace the original declaration with the clean one
                xml_content = clean_declaration + xml_content[decl_end + 2:]
            else:
                # Handle case where ?> is missing
                if self.debug_mode:
                    print("XML declaration is incomplete (missing ?>)")

                # Find a reasonable place to end the declaration
                possible_end = xml_content.find('<', 5)  # Find first tag after <?xml
                if possible_end > 5:
                    incomplete_decl = xml_content[:possible_end].strip()
                    if self.debug_mode:
                        print(f"Incomplete declaration: '{incomplete_decl}'")

                    # Replace with a standard declaration
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?>' + xml_content[possible_end:]
        else:
            # Add XML declaration if missing
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content
            if self.debug_mode:
                print("Added XML declaration as it was missing")

        # Continue with other preprocessing steps
        processed_content = xml_content
        iteration_count = 0
        max_iterations = 20  # Prevent infinite loops

        # First pass: simple attribute with unescaped quotes
        pattern = r'=\s*"([^"]*)"([^"]*)"([^"]*)"'
        while re.search(pattern, processed_content) and iteration_count < max_iterations:
            if self.debug_mode:
                print("Found unescaped quotes in attributes, fixing...")

            def replace_quotes(match):
                # Replace unescaped quotes with &quot;
                content = match.group(1) + match.group(2) + match.group(3)
                content = content.replace('"', '&quot;')
                return f'="{content}"'

            old_content = processed_content
            processed_content = re.sub(pattern, replace_quotes, processed_content)
            # Check if we actually made changes
            if old_content == processed_content:
                break
            iteration_count += 1

        # More aggressive fix for problematic files: replace all unescaped quotes in attributes
        processed_content = re.sub(r'="([^"]*)"', lambda m: f'="{m.group(1).replace("\"", "&quot;")}"',
                                   processed_content)

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
        processed_content = re.sub(r'=([^\s">]+)(\s|>)', r'="\1"\2', processed_content)

        # Fix missing closing tags - only for basic elements
        for tag_match in re.finditer(r'<([a-zA-Z0-9_:-]+)([^>]*)>', processed_content):
            tag_name = tag_match.group(1)
            # Check if self-closing or has a closing tag
            if not re.search(f'</{tag_name}>', processed_content) and not '/' in tag_match.group(2):
                processed_content += f'</{tag_name}>'
                if self.debug_mode:
                    print(f"Added missing closing tag for <{tag_name}>")

        # Final validation - ensure XML declaration is correct
        if processed_content.startswith('<?xml'):
            if '<?xml version="' not in processed_content or not re.match(r'<\?xml version="[^"]*"\?>',
                                                                          processed_content[:30]):
                if self.debug_mode:
                    print(f"WARNING: XML declaration still malformed: '{processed_content[:30]}'")
                    print("Forcing standard XML declaration")
                # Force a standard declaration
                if '?>' in processed_content[:50]:
                    end_idx = processed_content.find('?>')
                    processed_content = '<?xml version="1.0" encoding="UTF-8"?>' + processed_content[end_idx + 2:]

        if self.debug_mode:
            print(f"Final XML declaration: '{processed_content[:50]}'")

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
            # Try reading as text first, with binary fallback
            xml_content = None

            # First try UTF-8
            try:
                with open(xml_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    xml_content = f.read()
                    if self.debug_mode:
                        print(f"Successfully read file with UTF-8 encoding")
            except UnicodeDecodeError:
                pass

            # If that fails, try other encodings
            if not xml_content:
                encodings = ['latin-1', 'cp1252', 'iso-8859-1']
                for encoding in encodings:
                    try:
                        with open(xml_file_path, 'r', encoding=encoding, errors='replace') as f:
                            xml_content = f.read()
                            if self.debug_mode:
                                print(f"Successfully read file with {encoding} encoding")
                            break
                    except UnicodeDecodeError:
                        continue

            # Last resort: read as binary and decode
            if not xml_content:
                try:
                    with open(xml_file_path, 'rb') as f:
                        binary_content = f.read()
                        # Try to detect encoding from XML declaration
                        encoding = 'utf-8'  # Default
                        if binary_content.startswith(b'<?xml'):
                            encoding_match = re.search(b'encoding=["\']([^"\']+)["\']', binary_content[:200])
                            if encoding_match:
                                encoding = encoding_match.group(1).decode('ascii')

                        xml_content = binary_content.decode(encoding, errors='replace')
                        if self.debug_mode:
                            print(f"Read file in binary mode with {encoding} encoding")
                except Exception as bin_err:
                    raise Exception(f"Failed to read file in any mode: {bin_err}")

            # Check if it looks like XML
            if not (xml_content.strip().startswith('<?xml') or xml_content.strip().startswith('<')):
                raise ValueError("File does not appear to be XML")

            # Add special debug for PDI files
            if xml_file_path.lower().endswith('.pdi'):
                print("*** PDI FILE DETECTED: Enabling special processing mode ***")
                print(f"File size: {len(xml_content)} bytes")

                # Take a sample from the beginning of the file
                sample_size = min(500, len(xml_content))
                print(f"First {sample_size} characters:")
                for i in range(0, sample_size, 50):
                    chunk = xml_content[i:i + 50].replace('\n', '\\n')
                    print(f"  {i:04d}: {chunk}")

            # PDI specific handling
            if xml_file_path.lower().endswith('.pdi'):
                self.debug_mode = True  # Force debug mode for PDI files

            # Preprocess XML content to fix common issues
            processed_xml = self.preprocess_xml(xml_content)

            # Try different parsing approaches with fallbacks
            json_data = None

            # Approach 1: Try direct xmltodict parsing first (most tolerant)
            try:
                import xmltodict
                if self.debug_mode:
                    print("Trying xmltodict parsing...")

                # Parse with xmltodict which is more tolerant of malformed XML
                # Use force_list to handle array elements correctly
                force_list = {}  # TODO: Detect array elements from data

                # Add a more detailed error handler
                def handle_xml_error(err):
                    if self.debug_mode:
                        print(f"XMLDict parse error: {err}")
                    return True  # Continue parsing

                xml_dict = xmltodict.parse(
                    processed_xml,
                    attr_prefix=self.attribute_prefix,
                    cdata_key=self.text_key,
                    force_list=force_list,
                    process_namespaces=True,
                    namespaces={},  # Collapse all namespaces
                )
                json_data = xml_dict

                if self.debug_mode:
                    print("Successfully parsed with xmltodict")

            except Exception as xmltodict_err:
                if self.debug_mode:
                    print(f"xmltodict parsing failed: {str(xmltodict_err)}")

                # Try other parsing methods (ElementTree, lxml, etc.)
                try:
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
                                                fixed_line = problem_line[:col_num - 1] + ' ' + problem_line[col_num:]

                                            lines[line_num - 1] = fixed_line

                                            fixed_xml = '\n'.join(lines)
                                            try:
                                                root = ET.fromstring(fixed_xml)
                                                if self.debug_mode:
                                                    print("Successfully parsed after fixing specific character!")
                                            except Exception as fix_err:
                                                errors.append(f"Character fixing failed: {fix_err}")

                    if not root:
                        raise Exception(f"Failed to parse XML with multiple methods. Errors: {', '.join(errors)}")

                    # Convert to dictionary
                    json_data = self.xml_to_dict(root)

                except Exception as et_err:
                    if self.debug_mode:
                        print(f"ElementTree parsing failed: {str(et_err)}")
                    raise Exception(f"All parsing methods failed. Last error: {str(xmltodict_err)}")

            # Validate we have data
            if not json_data:
                raise Exception("Failed to extract any data from the XML file")

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
                print("*** DETAILED ERROR TRACEBACK ***")
                traceback.print_exc()
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
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
