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
        import time
        start_time = time.time()
        timeout_seconds = 30  # 30 second timeout

        if self.debug_mode:
            print(f"=== STARTING XML PREPROCESSING ===")
            print(f"Preprocessing XML content of length {len(xml_content)}")
            print(f"First 100 characters: {xml_content[:100].replace(chr(10), '\\n')}")

        # Check for timeout
        def check_timeout():
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"XML preprocessing timed out after {timeout_seconds} seconds")

        # FIXED: Simplified XML declaration handling
        if xml_content.startswith('<?xml'):
            check_timeout()
            # Find where the XML declaration ends
            decl_end = xml_content.find('?>')
            if decl_end > 0:
                # Extract everything after the XML declaration
                remaining_content = xml_content[decl_end + 2:]

                # Always use a standard, well-formed XML declaration
                clean_declaration = '<?xml version="1.0" encoding="UTF-8"?>'

                if self.debug_mode:
                    original_declaration = xml_content[:decl_end + 2]
                    print(f"Original declaration: '{original_declaration}'")
                    print(f"Cleaned declaration: '{clean_declaration}'")

                # Reconstruct with clean declaration
                xml_content = clean_declaration + remaining_content
            else:
                # Handle case where ?> is missing - find the first tag after <?xml
                possible_end = xml_content.find('<', 5)  # Find first tag after <?xml
                if possible_end > 5:
                    if self.debug_mode:
                        incomplete_decl = xml_content[:possible_end].strip()
                        print(f"Incomplete declaration found: '{incomplete_decl}'")

                    # Replace with standard declaration
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?>' + xml_content[possible_end:]
                else:
                    # If we can't find a reasonable place, just prepend standard declaration
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content[5:]
        else:
            # Add XML declaration if missing
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content
            if self.debug_mode:
                print("Added XML declaration as it was missing")

        # Continue with other preprocessing steps
        processed_content = xml_content
        check_timeout()
        iteration_count = 0
        max_iterations = 20  # Prevent infinite loops

        # DETAILED DEBUG: Let's see what's actually happening with quote fixing
        if self.debug_mode:
            print("\n=== STARTING QUOTE ANALYSIS ===")
            # Sample the first 2000 characters to look for quote patterns
            sample = processed_content[:2000]
            print(f"Sample content (first 2000 chars):\n{sample}")
            print("\n=== CHECKING FOR QUOTE PATTERNS ===")

        # Check for various quote patterns with detailed output
        malformed_patterns = {
            'consecutive_quotes': r'""',  # Simple consecutive quotes
            'attr_quote_issue': r'\w+\s*=\s*"[^"]*"[^>\s][^"]*"',  # attr="value"extra"
            'double_quote_attr': r'\w+\s*=\s*"[^"]*""[^"]*"',  # attr="value""more"
            'unescaped_quote': r'="[^"]*"[^"]*"',  # Simple unescaped quotes in attributes
        }

        quote_issues_found = []
        for pattern_name, pattern in malformed_patterns.items():
            matches = list(re.finditer(pattern, processed_content))
            if matches:
                quote_issues_found.append(pattern_name)
                if self.debug_mode:
                    print(f"Pattern '{pattern_name}': Found {len(matches)} matches")
                    # Show first few matches with context
                    for i, match in enumerate(matches[:3]):
                        start = max(0, match.start() - 30)
                        end = min(len(processed_content), match.end() + 30)
                        context = processed_content[start:end].replace('\n', '\\n')
                        print(f"  Match {i + 1}: ...{context}...")
                        print(f"    Position: {match.start()}-{match.end()}")
                        print(f"    Matched text: '{match.group()}'")

        if not quote_issues_found:
            if self.debug_mode:
                print("No quote issues detected - skipping quote fixing")
        else:
            if self.debug_mode:
                print(f"Quote issues found: {quote_issues_found}")
                print("Starting quote fixing process...")

            # Use the most conservative pattern - only fix obvious consecutive quotes
            quote_pattern = r'""'  # Just fix double quotes
            iteration_count = 0
            max_iterations = 5  # Very limited iterations

            while '""' in processed_content and iteration_count < max_iterations:
                check_timeout()  # Check for timeout

                if self.debug_mode:
                    double_quote_count = processed_content.count('""')
                    print(f"Iteration {iteration_count}: Found {double_quote_count} double quotes")

                    # Show where they are
                    positions = []
                    start = 0
                    for _ in range(min(5, double_quote_count)):  # Show first 5
                        pos = processed_content.find('""', start)
                        if pos == -1:
                            break
                        positions.append(pos)
                        start = pos + 1
                    print(f"  Double quote positions: {positions}")

                    # Show context for first few
                    for i, pos in enumerate(positions[:2]):
                        context_start = max(0, pos - 20)
                        context_end = min(len(processed_content), pos + 20)
                        context = processed_content[context_start:context_end].replace('\n', '\\n')
                        print(f"  Context {i + 1}: ...{context}...")

                old_content = processed_content
                old_length = len(processed_content)

                # Replace consecutive quotes with quote + escaped quote
                processed_content = processed_content.replace('""', '"&quot;', 10)  # Fix max 10 at a time

                if self.debug_mode:
                    changes_made = old_content != processed_content
                    new_length = len(processed_content)
                    print(f"  Changes made: {changes_made}")
                    print(f"  Length change: {old_length} -> {new_length} (diff: {new_length - old_length})")
                    if changes_made:
                        new_double_quote_count = processed_content.count('""')
                        print(f"  Double quotes remaining: {new_double_quote_count}")

                # Check if we actually made changes
                if old_content == processed_content:
                    if self.debug_mode:
                        print("  No changes made - breaking loop")
                    break

                # Safety check - if we're not making progress, break
                if iteration_count > 2 and processed_content.count('""') == double_quote_count:
                    if self.debug_mode:
                        print("  No progress made - breaking loop to prevent infinite loop")
                    break

                iteration_count += 1

            if self.debug_mode:
                final_double_quotes = processed_content.count('""')
                print(
                    f"Quote fixing complete. Iterations: {iteration_count}, Remaining double quotes: {final_double_quotes}")

        if self.debug_mode:
            print("=== QUOTE ANALYSIS COMPLETE ===\n")

        if self.debug_mode:
            print("=== CONTINUING WITH OTHER PREPROCESSING STEPS ===")

        # Fix standalone ampersands not part of entities
        if self.debug_mode:
            ampersand_count = len(re.findall(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)', processed_content))
            print(f"Fixing {ampersand_count} standalone ampersands...")

        processed_content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', processed_content)

        # Fix unclosed CDATA sections
        if '<![CDATA[' in processed_content and ']]>' not in processed_content:
            if self.debug_mode:
                print("Found unclosed CDATA section, fixing...")
            processed_content = processed_content.replace('<![CDATA[', '')

        # Remove control characters that might cause XML parsing issues
        if self.debug_mode:
            control_chars = re.findall(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', processed_content)
            if control_chars:
                print(f"Removing {len(control_chars)} control characters...")

        processed_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', processed_content)

        # Handle malformed attributes (values without quotes) - IMPROVED
        if self.debug_mode:
            unquoted_attrs = re.findall(r'(\w+\s*=\s*)([^\s">][^\s>]*?)(\s|>)', processed_content)
            if unquoted_attrs:
                print(f"Found {len(unquoted_attrs)} potentially unquoted attributes, fixing...")
                for i, attr in enumerate(unquoted_attrs[:3]):  # Show first 3
                    print(f"  Unquoted attr {i + 1}: {attr[0]}{attr[1]}{attr[2]}")

        # Only match attribute values that are clearly unquoted (not already within quotes)
        processed_content = re.sub(r'(\w+\s*=\s*)([^\s">][^\s>]*?)(\s|>)', r'\1"\2"\3', processed_content)

        if self.debug_mode:
            final_declaration = processed_content[:50].split('\n')[0] if '\n' in processed_content[
                                                                                 :50] else processed_content[:50]
            print(f"Final XML declaration: '{final_declaration}'")
            print("=== PREPROCESSING COMPLETE ===\n")

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
                    chunk = xml_content[i:i+50].replace('\n', '\\n')
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
                                                fixed_line = problem_line[:col_num-1] + ' ' + problem_line[col_num:]

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
