import json
import re
import sys

def parse_documents(text):
    documents = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('<DOCUMENT filename='):
            match = re.search(r'<DOCUMENT filename="([^"]+)"', line)
            if match:
                filename = match.group(1)
            else:
                i += 1
                continue
            content_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('</DOCUMENT>'):
                content_lines.append(lines[i])
                i += 1
            documents.append({'filename': filename, 'content_lines': content_lines})
        else:
            i += 1
    return documents

def parse_layout(content_lines, filename):
    layout = {'metadata': {}, 'fields': [], 'text': []}
    i = 0
    while i < len(content_lines):
        line = content_lines[i].strip()
        if line.startswith('PA'):
            tag = line
            content = []
            i += 1
            while i < len(content_lines):
                l = content_lines[i].strip()
                if l.startswith('PA'):
                    break
                content.append(l)
                i += 1
            if tag.startswith('PA2087::'):
                if len(content) >= 8:
                    idx_shift = 0
                    if content[2] == '':
                        idx_shift = 1
                    layout['metadata']['main'] = {
                        '@ID': tag,
                        'FORMNO': content[0],
                        'FIELDNAME': content[1],
                        'POSNO': content[2 + idx_shift],
                        'WIDTH': content[3 + idx_shift],
                        'ISOUTPUT': content[4 + idx_shift],
                        'FONT': content[5 + idx_shift],
                        'ORIENTATION': content[6 + idx_shift],
                        'OP': content[7 + idx_shift]
                    }
            elif tag.startswith('PA2090'):
                if len(content) <= 5:
                    text_value = content[0] if content else ''
                    formno = content[1] if len(content) > 1 else ''
                    var = content[2] if len(content) > 2 else ''
                    stripped_text = text_value.strip()
                    if var in ['C', 'D'] and stripped_text and stripped_text != ';':
                        text = {
                            '@ID': tag,
                            'VARIABLE': text_value,
                            'FORMNO': formno,
                            'VARIANT': var
                        }
                        layout['text'].append(text)
                else:
                    triple_index = -1
                    for j in range(len(content) - 2):
                        if content[j] == 'false' and content[j + 1] == 'false' and content[j + 2] == 'true':
                            triple_index = j
                            break
                    if triple_index == -1:
                        continue
                    pre = content[:triple_index]
                    mask = pre[-2] if len(pre) >= 2 else ''
                    length = pre[-1] if len(pre) >= 1 else ''
                    isoutput = content[triple_index]
                    ismandatory = content[triple_index + 1]
                    isactive = content[triple_index + 2]
                    post = content[triple_index + 3:]
                    posno = pre[0] if pre else ''
                    parent = pre[1] if len(pre) > 1 else ''
                    group = pre[2] if len(pre) > 2 else ''
                    type_ = pre[3] if len(pre) > 3 else ''
                    value = pre[4] if len(pre) > 4 else ''
                    if mask in ['T', 'I', '-', ''] or (len(mask) == 1 and not mask.isdigit()):
                        type_ = mask
                        value = length
                        mask = ''
                        length = ''
                    variable = post[0] if post and post[0] in ['', ';', '-'] else ''
                    fieldname = post[-2] if len(post) >= 2 and post[-2].startswith('PA') else ''
                    formno = post[-1] if post else ''
                    field = {
                        '@ID': tag,
                        'POSNO': posno,
                        'PARENT': parent,
                        'GROUP': group,
                        'TYPE': type_,
                        'VALUE': value,
                        'MASK': mask,
                        'LENGTH': length,
                        'ISOUTPUT': isoutput,
                        'ISMANDATORY': ismandatory,
                        'ISACTIVE': isactive,
                        'VARIABLE': variable,
                        'FIELDNAME': fieldname,
                        'FORMNO': formno
                    }
                    layout['fields'].append(field)
        else:
            i += 1
    parts = re.split(r'\$', filename)
    if len(parts) >= 3:
        variant = parts[1].upper()
        formno_str = parts[2].split('_')[0]
        if 'main' in layout['metadata']:
            layout['metadata']['main']['VARIANT'] = variant
            layout['metadata']['main']['FORMNO_STR'] = formno_str
    return layout

if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            input_text = f.read()
    else:
        input_text = sys.stdin.read()
    documents = parse_documents(input_text)
    results = []
    for doc in documents:
        layout = parse_layout(doc['content_lines'], doc['filename'])
        results.append({'filename': doc['filename'], 'layout': layout})
    print(json.dumps(results, indent=2, ensure_ascii=False))