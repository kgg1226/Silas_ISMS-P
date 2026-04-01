"""Fetch and parse ISMS-P defect cases from meganad.github.io"""
import urllib.request
import html.parser
import json
import sys


class ISMSParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.subtitle = ''
        self.in_h1 = False
        self.in_h2_sub = False
        self.in_h3 = False
        self.in_strong = False
        self.in_article = False
        self.in_defect_list = False
        self.in_li = False
        self.in_check_list = False
        self.current_section = ''
        self.defects = []
        self.checks = []
        self.key_point = ''
        self.current_text = ''
        self.h3_text = ''
        self.h3_active = False
        self.li_depth = 0
        self.found_post_heading = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == 'div' and attr_dict.get('class', '') == 'post-heading':
            self.found_post_heading = True
        if tag == 'h1' and self.found_post_heading:
            self.in_h1 = True
            self.current_text = ''
        elif tag == 'h2' and 'post-subheading' in attr_dict.get('class', ''):
            self.in_h2_sub = True
            self.current_text = ''
        elif tag == 'h3':
            self.in_h3 = True
            self.h3_text = ''
        elif tag == 'strong' and self.current_section == '주요사항':
            self.in_strong = True
            self.current_text = ''
        elif tag == 'li':
            if self.in_defect_list:
                self.in_li = True
                self.li_depth += 1
                if self.li_depth == 1:
                    self.current_text = ''
            elif self.in_check_list:
                self.in_li = True
                self.li_depth += 1
                if self.li_depth == 1:
                    self.current_text = ''

    def handle_endtag(self, tag):
        if tag == 'h1' and self.in_h1:
            self.in_h1 = False
            self.title = self.current_text.strip()
        elif tag == 'h2' and self.in_h2_sub:
            self.in_h2_sub = False
            self.subtitle = self.current_text.strip()
        elif tag == 'h3':
            self.in_h3 = False
            section = self.h3_text.strip()
            self.current_section = section
            if section == '결함사례':
                self.in_defect_list = True
                self.in_check_list = False
            elif section == '확인사항':
                self.in_check_list = True
                self.in_defect_list = False
            else:
                self.in_defect_list = False
                self.in_check_list = False
        elif tag == 'strong' and self.in_strong:
            self.in_strong = False
            self.key_point = self.current_text.strip()
        elif tag == 'li' and self.in_li:
            self.li_depth -= 1
            if self.li_depth == 0:
                self.in_li = False
                t = self.current_text.strip()
                if t:
                    if self.in_defect_list:
                        self.defects.append(t)
                    elif self.in_check_list:
                        self.checks.append(t)
        elif tag == 'ul':
            if self.in_defect_list:
                self.in_defect_list = False
            elif self.in_check_list:
                self.in_check_list = False
        elif tag == 'hr':
            self.in_defect_list = False
            self.in_check_list = False

    def handle_data(self, data):
        if self.in_h1:
            self.current_text += data
        elif self.in_h2_sub:
            self.current_text += data
        elif self.in_h3:
            self.h3_text += data
        elif self.in_strong and self.current_section == '주요사항':
            self.current_text += data
        elif self.in_li:
            self.current_text += data


urls = [
    'https://meganad.github.io/ISMS-P/CERT/1.2.2',
    'https://meganad.github.io/ISMS-P/CERT/1.2.3',
    'https://meganad.github.io/ISMS-P/CERT/1.2.4',
    'https://meganad.github.io/ISMS-P/CERT/1.3.1',
    'https://meganad.github.io/ISMS-P/CERT/1.3.2',
    'https://meganad.github.io/ISMS-P/CERT/1.3.3',
    'https://meganad.github.io/ISMS-P/CERT/1.4.1',
    'https://meganad.github.io/ISMS-P/CERT/1.4.2',
    'https://meganad.github.io/ISMS-P/CERT/1.4.3',
    'https://meganad.github.io/ISMS-P/CERT/2.1.1',
    'https://meganad.github.io/ISMS-P/CERT/2.1.2',
    'https://meganad.github.io/ISMS-P/CERT/2.1.3',
    'https://meganad.github.io/ISMS-P/CERT/2.10.6',
    'https://meganad.github.io/ISMS-P/CERT/2.2.1',
    'https://meganad.github.io/ISMS-P/CERT/3.1.6',
]

results = {}

for url in urls:
    code = url.split('/CERT/')[-1]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_content = resp.read().decode('utf-8')

        parser = ISMSParser()
        parser.feed(html_content)

        results[code] = {
            'title': parser.title,
            'category': parser.subtitle,
            'key_point': parser.key_point,
            'checks': parser.checks,
            'defects': parser.defects,
        }
        print(f"[OK] {code}: {parser.title} - {len(parser.defects)} defects, {len(parser.checks)} checks", file=sys.stderr)
    except Exception as e:
        results[code] = {'error': str(e)}
        print(f"[ERR] {code}: {e}", file=sys.stderr)

# Output JSON
print(json.dumps(results, ensure_ascii=False, indent=2))
