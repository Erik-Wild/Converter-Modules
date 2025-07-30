import xml.etree.ElementTree as ET
import os
import json
import logging
import copy
import shutil
from typing import Dict, Any, List, Optional
import re

# Configure logging
logging.basicConfig(level=logging.INFO, filename='json_to_listlabel_conversion.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')


class JsonToListLabelConverter:
    """Converts JSON files to List & Label .pdi format"""

    def __init__(self, template_path: str = "Empty_List_Label.pdi", additional_files: List[str] = None):
        print(f"[DEBUG] JsonToListLabelConverter init:")
        print(f"  template_path: {template_path}")
        print(f"  additional_files: {additional_files}")

        # Use additional_files from pipeline if provided
        template_file = None
        if additional_files:
            print(f"[DEBUG] Searching for Empty_List_Label.pdi in additional_files:")
            for f in additional_files:
                print(f"  Checking: {f}")
                if os.path.basename(f).lower() == "empty_list_label.pdi":
                    template_file = f
                    print(f"  Found template file: {template_file}")
                    break

        if template_file and os.path.exists(template_file):
            template_path = template_file
            print(f"[DEBUG] Using template from additional_files: {template_path}")
        else:
            print(f"[DEBUG] Template not found in additional_files, using fallback: {template_path}")
            # Fallback to previous search logic
            possible_paths = [
                template_path,
                os.path.join(os.getcwd(), "Empty_List_Label.pdi"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "Empty_List_Label.pdi"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "examples",
                             "Empty_List_Label.pdi"),
            ]
            found = False
            for path in possible_paths:
                print(f"[DEBUG] Checking fallback path: {path}")
                if os.path.exists(path):
                    template_path = path
                    found = True
                    print(f"[DEBUG] Found template at: {template_path}")
                    break
            if not found:
                raise FileNotFoundError(f"Template file Empty_List_Label.pdi not found in any of: {possible_paths}")

        self.template_path = template_path
        print(f"[DEBUG] Final template path: {self.template_path}")

        # Store the original template content as text to preserve formatting
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template_content = f.read()

        # Load the template for manipulation
        try:
            self.template_tree = ET.parse(template_path)
            self.template_root = self.template_tree.getroot()
            print(f"[DEBUG] Template loaded successfully")
        except ET.ParseError as e:
            logging.error(f"Failed to parse template file {template_path}: {str(e)}")
            print(f"[ERROR] Failed to parse template file {template_path}: {str(e)}")
            raise

    def convert_file(self, json_file_path: str, output_path: str = None) -> str:
        """
        Convert JSON file to List & Label .pdi format

        Args:
            json_file_path: Path to input JSON file
            output_path: Path for output .pdi file (optional)

        Returns:
            Path to generated .pdi file
        """
        try:
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Create output path if not specified
            if not output_path:
                base_name = os.path.splitext(os.path.basename(json_file_path))[0]
                output_path = os.path.join(os.path.dirname(json_file_path), f"{base_name}.pdi")

            # Create a copy of the template
            new_tree = copy.deepcopy(self.template_tree)
            new_root = new_tree.getroot()

            # Apply data from JSON to the template
            self._apply_json_to_template(new_root, data)

            # Write the modified template with preserved formatting
            self._write_with_preserved_formatting(new_tree, output_path)

            logging.info(f"Successfully converted {json_file_path} to {output_path}")
            return output_path

        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in {json_file_path}: {str(e)}")
            raise Exception(f"Failed to parse JSON in {json_file_path}: {str(e)}")
        except Exception as e:
            logging.error(f"Error converting {json_file_path}: {str(e)}")
            raise Exception(f"Error converting JSON to List & Label: {str(e)}")

    def _write_with_preserved_formatting(self, tree: ET.ElementTree, output_path: str) -> None:
        """Write XML with preserved namespace prefixes and formatting"""
        # First, let's write using ElementTree to get the structure
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as tmp_file:
            tree.write(tmp_file.name, encoding='utf-8', xml_declaration=True)
            temp_path = tmp_file.name

        # Read the generated content
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Clean up temp file
        os.unlink(temp_path)

        # Fix the namespace prefixes and formatting
        content = self._fix_xml_formatting(content)

        # Write the corrected content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _fix_xml_formatting(self, content: str) -> str:
        """Fix XML formatting to match the expected output"""
        # Fix XML declaration
        content = re.sub(r'<\?xml version=\'([^\']+)\' encoding=\'([^\']+)\'\?>',
                         r'<?xml version="\1"?>', content)

        # Fix namespace declarations in root element
        # Replace the generated root element with the correct one
        root_pattern = r'<dsBG_Form[^>]*>'
        expected_root = '<dsBG_Form xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        content = re.sub(root_pattern, expected_root, content)

        # Fix namespace prefixes throughout the document
        # Replace ns0: with xsd: and ns1: with prodata: etc.
        content = re.sub(r'xmlns:ns\d+="http://www\.w3\.org/2001/XMLSchema"', '', content)
        content = re.sub(r'xmlns:ns\d+="urn:schemas-progress-com:xml-prodata:0001"', '', content)
        content = re.sub(r'<ns\d+:', '<xsd:', content)
        content = re.sub(r'</ns\d+:', '</xsd:', content)
        content = re.sub(r'<xs:', '<xsd:', content)
        content = re.sub(r'</xs:', '</xsd:', content)

        # Fix prodata namespace attributes - this is the key fix
        content = re.sub(r'ns\d+:proDataSet', 'prodata:proDataSet', content)
        content = re.sub(r'ns\d+:beforeTable', 'prodata:beforeTable', content)
        content = re.sub(r'ns\d+:format', 'prodata:format', content)
        content = re.sub(r'ns\d+:columnLabel', 'prodata:columnLabel', content)
        content = re.sub(r'ns\d+:label', 'prodata:label', content)
        content = re.sub(r'ns\d+:help', 'prodata:help', content)

        # Fix the schema element to include proper namespace declarations including empty default namespace
        schema_pattern = r'<xsd:schema[^>]*>'
        expected_schema = ('  <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
                           'xmlns="" xmlns:prodata="urn:schemas-progress-com:xml-prodata:0001">')
        content = re.sub(schema_pattern, expected_schema, content)

        # Clean up any duplicate or malformed namespace declarations
        # Remove extra namespace declarations that might have been added
        content = re.sub(r'\s+xmlns:xsi="[^"]*"(?=.*xmlns:xsi)', '', content)  # Remove duplicate xsi
        content = re.sub(r'\s+xmlns="[^"]*"(?=.*xmlns="")', '', content)  # Remove duplicate default ns

        # Ensure proper spacing and formatting
        # Fix self-closing tags to have space before />
        content = re.sub(r'([^/\s])/>', r'\1 />', content)

        # Fix spacing around attributes to match expected format
        content = re.sub(r'"\s+([a-zA-Z])', r'" \1', content)

        return content

    def _apply_json_to_template(self, root: ET.Element, data: Dict[str, Any]) -> None:
        """Apply JSON data to the template"""
        # Extract form information
        form_info = data.get('form', {})

        # Update ttBG_FKopf element
        if form_info and self._find_element(root, 'ttBG_FKopf'):
            kopf_elem = self._find_element(root, 'ttBG_FKopf')

            # Set form identification
            if 'Firma' in form_info:
                self._update_element_text(kopf_elem, 'Firma', str(form_info['Firma']))
            if 'Formular' in form_info:
                self._update_element_text(kopf_elem, 'Formular', str(form_info['Formular']))
            if 'FormularNr' in form_info:
                self._update_element_text(kopf_elem, 'FormularNr', str(form_info['FormularNr']))

            # Set layout information
            if 'Anzahl_Zeilen' in form_info:
                self._update_element_text(kopf_elem, 'Anzahl_Zeilen', str(form_info['Anzahl_Zeilen']))
            if 'Anzahl_Spalten' in form_info:
                self._update_element_text(kopf_elem, 'Anzahl_Spalten', str(form_info['Anzahl_Spalten']))
            if 'Generatortyp' in form_info:
                self._update_element_text(kopf_elem, 'Generatortyp', str(form_info['Generatortyp']))

        # Update language descriptions
        if 'descriptions' in data and isinstance(data['descriptions'], list):
            for desc in data['descriptions']:
                language = desc.get('language', 'D')
                text = desc.get('text', '')

                # Find or create a ttBG_FKopfSpr element for this language
                self._update_description(root, language, text)

        # Create sections from JSON data
        if 'sections' in data and isinstance(data['sections'], list):
            for section_data in data['sections']:
                self._create_section(root, section_data)

        # Add fields from JSON data
        if 'fields' in data and isinstance(data['fields'], list):
            for field_data in data['fields']:
                self._create_field(root, field_data)

        # Add text elements from JSON data
        if 'texts' in data and isinstance(data['texts'], list):
            for text_data in data['texts']:
                self._create_text(root, text_data)

    def _find_element(self, parent: ET.Element, tag_name: str) -> Optional[ET.Element]:
        """Find first element with given tag name"""
        return parent.find(tag_name)

    def _update_element_text(self, parent: ET.Element, tag_name: str, text: str) -> None:
        """Update text of element with given tag name"""
        elem = parent.find(tag_name)
        if elem is not None:
            elem.text = text

    def _update_description(self, root: ET.Element, language: str, text: str) -> None:
        """Update or create language description"""
        # Look for existing description for this language
        for desc_elem in root.findall('ttBG_FKopfSpr'):
            if desc_elem.find('Sprache') is not None and desc_elem.find('Sprache').text == language:
                # Update existing description
                bezeichnung_elem = desc_elem.find('Bezeichnung')
                if bezeichnung_elem is not None:
                    bezeichnung_elem.text = text
                return

        # No existing description found, create a new one
        kopf_elem = self._find_element(root, 'ttBG_FKopf')
        if kopf_elem is not None:
            firma = kopf_elem.find('Firma').text if kopf_elem.find('Firma') is not None else '1'
            formular = kopf_elem.find('Formular').text if kopf_elem.find('Formular') is not None else ''
            formular_nr = kopf_elem.find('FormularNr').text if kopf_elem.find('FormularNr') is not None else '0'

            desc_elem = ET.SubElement(root, 'ttBG_FKopfSpr')
            ET.SubElement(desc_elem, 'Firma').text = firma
            ET.SubElement(desc_elem, 'Formular').text = formular
            ET.SubElement(desc_elem, 'FormularNr').text = formular_nr
            ET.SubElement(desc_elem, 'Sprache').text = language
            ET.SubElement(desc_elem, 'Bezeichnung').text = text

    def _create_section(self, root: ET.Element, section_data: Dict[str, Any]) -> None:
        """Create a section element from JSON data"""
        section_id = section_data.get('id', '')
        if not section_id:
            logging.warning("Skipping section without id")
            return

        # Get form information from ttBG_FKopf
        kopf_elem = self._find_element(root, 'ttBG_FKopf')
        if kopf_elem is None:
            logging.warning("No ttBG_FKopf element found")
            return

        firma = kopf_elem.find('Firma').text if kopf_elem.find('Firma') is not None else '1'
        formular = kopf_elem.find('Formular').text if kopf_elem.find('Formular') is not None else ''
        formular_nr = kopf_elem.find('FormularNr').text if kopf_elem.find('FormularNr') is not None else '0'

        # Create a new section
        section_elem = ET.SubElement(root, 'ttBG_FAbschnitt')
        ET.SubElement(section_elem, 'Firma').text = firma
        ET.SubElement(section_elem, 'Formular').text = formular
        ET.SubElement(section_elem, 'FormularNr').text = formular_nr
        ET.SubElement(section_elem, 'Abschnitt').text = section_id

        # Add section properties
        if 'fruehester_Beginn' in section_data:
            ET.SubElement(section_elem, 'fruehester_Beginn').text = str(section_data['fruehester_Beginn'])
        if 'spaetester_Beginn' in section_data:
            ET.SubElement(section_elem, 'spaetester_Beginn').text = str(section_data['spaetester_Beginn'])
        if 'spaetestes_Ende' in section_data:
            ET.SubElement(section_elem, 'spaetestes_Ende').text = str(section_data['spaetestes_Ende'])

        # Generate a unique object ID
        obj_id = f"PA0170:zWLD:{section_id}_{formular_nr}_{formular}"
        ET.SubElement(section_elem, 'BG_FAbschnitt_Obj').text = obj_id

    def _create_field(self, root: ET.Element, field_data: Dict[str, Any]) -> None:
        """Create a field element from JSON data"""
        field_id = field_data.get('id', '')
        section_id = field_data.get('section', '')
        subsection_id = field_data.get('subsection', '')

        if not field_id or not section_id:
            logging.warning("Skipping field without id or section")
            return

        # Get form information from ttBG_FKopf
        kopf_elem = self._find_element(root, 'ttBG_FKopf')
        if kopf_elem is None:
            logging.warning("No ttBG_FKopf element found")
            return

        firma = kopf_elem.find('Firma').text if kopf_elem.find('Firma') is not None else '1'
        formular = kopf_elem.find('Formular').text if kopf_elem.find('Formular') is not None else ''
        formular_nr = kopf_elem.find('FormularNr').text if kopf_elem.find('FormularNr') is not None else '0'

        # Create a new field
        field_elem = ET.SubElement(root, 'ttBG_FFeld')
        ET.SubElement(field_elem, 'Firma').text = firma
        ET.SubElement(field_elem, 'Formular').text = formular
        ET.SubElement(field_elem, 'FormularNr').text = formular_nr
        ET.SubElement(field_elem, 'Abschnitt').text = section_id
        ET.SubElement(field_elem, 'UnterAbschnitt').text = subsection_id

        # Add field properties
        if 'FeldTyp' in field_data:
            ET.SubElement(field_elem, 'FeldTyp').text = field_data['FeldTyp']
        if 'TabellenName' in field_data:
            ET.SubElement(field_elem, 'TabellenName').text = field_data['TabellenName']
        if 'SpaltenName' in field_data:
            ET.SubElement(field_elem, 'SpaltenName').text = field_data['SpaltenName']
        if 'ZusatzInfo' in field_data:
            ET.SubElement(field_elem, 'ZusatzInfo').text = field_data['ZusatzInfo']
        if 'Zeile' in field_data:
            ET.SubElement(field_elem, 'Zeile').text = str(field_data['Zeile'])
        if 'Spalte' in field_data:
            ET.SubElement(field_elem, 'Spalte').text = str(field_data['Spalte'])
        if 'FeldNummer' in field_data:
            ET.SubElement(field_elem, 'FeldNummer').text = str(field_data['FeldNummer'])
        else:
            ET.SubElement(field_elem, 'FeldNummer').text = field_id
        if 'FeldFormat' in field_data:
            ET.SubElement(field_elem, 'FeldFormat').text = field_data['FeldFormat']
        if 'Druckstellen' in field_data:
            ET.SubElement(field_elem, 'Druckstellen').text = str(field_data['Druckstellen'])

        # Add field translations if provided
        if 'translations' in field_data and isinstance(field_data['translations'], list):
            for trans in field_data['translations']:
                language = trans.get('language', 'D')
                text = trans.get('text', '')
                format_text = trans.get('format', '')

                # Create field translation
                trans_elem = ET.SubElement(root, 'ttBG_FFeldSpr')
                ET.SubElement(trans_elem, 'Firma').text = firma
                ET.SubElement(trans_elem, 'Formular').text = formular
                ET.SubElement(trans_elem, 'FormularNr').text = formular_nr
                ET.SubElement(trans_elem, 'Abschnitt').text = section_id
                ET.SubElement(trans_elem, 'UnterAbschnitt').text = subsection_id
                ET.SubElement(trans_elem, 'FeldNummer').text = field_elem.find('FeldNummer').text
                ET.SubElement(trans_elem, 'Sprache').text = language
                ET.SubElement(trans_elem, 'Feldinhalt').text = text
                if format_text:
                    ET.SubElement(trans_elem, 'FeldFormat').text = format_text

        # Generate a unique object ID
        obj_id = f"PA0172:zWLD:{field_id}_{formular_nr}_{section_id}"
        ET.SubElement(field_elem, 'BG_FFeld_Obj').text = obj_id

    def _create_text(self, root: ET.Element, text_data: Dict[str, Any]) -> None:
        """Create a text element from JSON data"""
        text_art = text_data.get('TextArt', '')
        schluessel = text_data.get('Schluessel', '')

        if not text_art:
            logging.warning("Skipping text without TextArt")
            return

        # Get form information from ttBG_FKopf
        kopf_elem = self._find_element(root, 'ttBG_FKopf')
        if kopf_elem is None:
            logging.warning("No ttBG_FKopf element found")
            return

        firma = kopf_elem.find('Firma').text if kopf_elem.find('Firma') is not None else '1'
        formular = kopf_elem.find('Formular').text if kopf_elem.find('Formular') is not None else ''
        formular_nr = kopf_elem.find('FormularNr').text if kopf_elem.find('FormularNr') is not None else '0'

        # Create a new text element
        text_elem = ET.SubElement(root, 'ttBG_FText')
        ET.SubElement(text_elem, 'Firma').text = firma
        ET.SubElement(text_elem, 'Formular').text = formular
        ET.SubElement(text_elem, 'FormularNr').text = formular_nr
        ET.SubElement(text_elem, 'TextArt').text = text_art
        ET.SubElement(text_elem, 'Schluessel').text = schluessel

        # Generate a unique object ID
        obj_id = f"PA0171:zWLD:{text_art}_{schluessel}_{formular_nr}"
        ET.SubElement(text_elem, 'BG_FText_Obj').text = obj_id

        # Add text content if provided
        if 'content' in text_data and isinstance(text_data['content'], dict):
            for language, content in text_data['content'].items():
                text_kopf_elem = ET.SubElement(root, 'ttBT_Kopf')
                ET.SubElement(text_kopf_elem, 'TextArt').text = text_art
                ET.SubElement(text_kopf_elem, 'Sprache').text = language
                ET.SubElement(text_kopf_elem, 'Firma').text = firma
                ET.SubElement(text_kopf_elem, 'Owning_Obj').text = obj_id
                ET.SubElement(text_kopf_elem, 'PlainText').text = content

                # Generate a unique object ID for the text content
                text_obj_id = f"PA0174:zWLD:{text_art}_{schluessel}_{language}"
                ET.SubElement(text_kopf_elem, 'BT_Kopf_Obj').text = text_obj_id


def convert(input_files: List[str], output_dir: str = None, template_path: str = "Empty_List_Label.pdi",
            additional_files: List[str] = None, **options) -> List[str]:
    """
    Main conversion function for the module system

    Args:
        input_files: List of JSON file paths to convert
        output_dir: Directory for output .pdi files
        template_path: Path to the template .pdi file
        additional_files: List of additional files from pipeline
        **options: Additional conversion options

    Returns:
        List of generated .pdi file paths
    """
    print(f"[DEBUG] convert() called with:")
    print(f"  input_files: {input_files}")
    print(f"  output_dir: {output_dir}")
    print(f"  template_path: {template_path}")
    print(f"  additional_files: {additional_files}")
    print(f"  options: {options}")

    try:
        converter = JsonToListLabelConverter(template_path, additional_files)
    except Exception as e:
        logging.error(f"Failed to initialize converter: {str(e)}")
        print(f"[ERROR] Failed to initialize converter: {str(e)}")
        return []

    output_files = []

    for input_file in input_files:
        print(f"[DEBUG] Processing input file: {input_file}")
        try:
            if not input_file.lower().endswith('.json'):
                logging.warning(f"Skipping non-JSON file: {input_file}")
                print(f"[WARNING] Skipping non-JSON file: {input_file}")
                continue

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                filename = os.path.basename(input_file).rsplit('.', 1)[0] + '.pdi'
                output_path = os.path.join(output_dir, filename)
            else:
                output_path = None

            print(f"[DEBUG] Converting to output path: {output_path}")
            result_path = converter.convert_file(input_file, output_path)
            output_files.append(result_path)
            print(f"[DEBUG] Successfully converted to: {result_path}")

        except Exception as e:
            logging.error(f"Error converting {input_file}: {str(e)}")
            print(f"[ERROR] Error converting {input_file}: {str(e)}")

    print(f"[DEBUG] convert() returning: {output_files}")
    return output_files


if __name__ == "__main__":
    # Test the converter with example JSON files
    import glob

    # Find all JSON files in the examples directory
    example_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "examples")
    json_files = glob.glob(os.path.join(example_dir, "*.json"))

    if not json_files:
        print(f"No JSON files found in {example_dir}")
    else:
        print(f"Found {len(json_files)} JSON files in {example_dir}")
        template_path = os.path.join(example_dir, "Empty_List_Label.pdi")

        # Check if template exists, otherwise use the one in the current directory
        if not os.path.exists(template_path):
            template_path = "Empty_List_Label.pdi"
            if not os.path.exists(template_path):
                print(f"Template file not found: {template_path}")
                exit(1)

        results = convert(json_files, output_dir="converted_templates", template_path=template_path)
        print(f"Converted files: {results}")