import unittest
from peppercorn.compat import PY3

class TestParse(unittest.TestCase):
    def _callFUT(self, fields):
        from peppercorn import parse
        return parse(fields)
        
    def _makeEnviron(self, kw=None):
        if kw is None: # pragma: no cover
            kw = {}
        env = {
            'wsgi.url_scheme': 'http',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8080',
            'REQUEST_METHOD':'POST',
            'PATH_INFO': '/',
            'QUERY_STRING':'',
            }
        env.update(kw)
        return env

    def _makeMultipartFieldStorage(self, fields):
        from cgi import FieldStorage
        ct, body = encode_multipart_formdata(fields)
        kw = dict(CONTENT_TYPE=ct, REQUEST_METHOD='POST')
        if PY3: # pragma: no cover
            from io import BytesIO
            fp = BytesIO(body.encode('utf-8'))
        else:
            from StringIO import StringIO
            fp = StringIO(body)
        environ = self._makeEnviron(kw)
        headers = {'content-length': "%d" % len(body), "content-type": ct}
        return FieldStorage(fp=fp, environ=environ, keep_blank_values=1, 
                            headers=headers)

    def _getFields(self):
        from peppercorn import START, END, MAPPING, SEQUENCE
        fields = [
            ('name', 'project1'),
            ('title', 'Cool project'),
            (START, 'series:%s' % MAPPING),
            ('name', 'date series 1'),
            (START, 'dates:%s' % SEQUENCE),
            (START, 'date:%s' % SEQUENCE),
            ('day', '10'),
            ('month', '12'),
            ('year', '2008'),
            (END, 'date:%s' % SEQUENCE),
            (START, 'date:%s' % SEQUENCE),
            ('day', '10'),
            ('month', '12'),
            ('year', '2009'),
            (END, 'date:%s' % SEQUENCE),
            (END, 'dates:%s' % SEQUENCE),
            (END, 'series:%s' % MAPPING),
            ]
        return fields

    def _assertFieldsResult(self, result):
        self.assertEqual(
            result,
            {'series':
             {'name':'date series 1',
              'dates': [['10', '12', '2008'],
                        ['10', '12', '2009']],
              },
             'name': 'project1',
             'title': 'Cool project'})

    def test_bare(self):
        fields = self._getFields()
        result = self._callFUT(fields)
        self._assertFieldsResult(result)
        
    def test_fieldstorage(self):
        fs = self._makeMultipartFieldStorage(self._getFields())

        fields = []
        if fs.list:
            for field in fs.list:
                fields.append((field.name, field.value))
        result = self._callFUT(fields)
        self._assertFieldsResult(result)

    def test_bad_start_marker(self):
        from peppercorn import START, ParseError
        fields = [
            (START, 'something:unknown'),
            ]
        
        self.assertRaises(ParseError, self._callFUT, fields)

    def test_unnamed_start_marker(self):
        from peppercorn import START, END, MAPPING
        fields = [
            (START, MAPPING),
            ('name', 'fred'),
            (END, ''),
            ]

        result = self._callFUT(fields)
        self.assertEqual(result, {'': {'name':'fred'}})

    def test_rename(self):
        from peppercorn import START, END, RENAME, MAPPING
        fields = [
            (START, MAPPING),
            (START, 'name:' + RENAME),
            ('bleev', 'fred'),
            ('blam', 'joe'),
            ('bloov', 'bob'),
            (END, ''),
            (END, ''),
            ]

        result = self._callFUT(fields)
        self.assertEqual(result, {'': {'name':'fred'}})
        
    def test_rename_no_subelements(self):
        from peppercorn import START, END, RENAME, MAPPING
        fields = [
            (START, MAPPING),
            (START, 'name:' + RENAME),
            (END, ''),
            (END, ''),
            ]

        result = self._callFUT(fields)
        self.assertEqual(result, {'': {'name':''}})

    def test_unclosed_sequence(self):
        from peppercorn import START, MAPPING, ParseError
        fields = [
            ('name', 'fred'),
            (START, 'series:%s' % MAPPING),
        ]
        self.assertRaises(ParseError, self._callFUT, fields)

    def test_deep_nesting(self):
        import sys
        from peppercorn import START, END, MAPPING, ParseError
        depth = sys.getrecursionlimit()
        # Create a valid input nested deeper than the recursion limit:
        fields = [(START, 'x:' + MAPPING)] * depth + [(END, '')] * depth
        self.assertRaises(ParseError, self._callFUT, fields)

    def test_spurios_initial_end(self):
        from peppercorn import END
        fields = [
            (END, ''),
            ('name', 'fred'),
        ]
        result = self._callFUT(fields)
        self.assertEqual(result, {})

    def test_spurious_intermediary_end(self):
        from peppercorn import START, SEQUENCE, END
        fields = [
            (START, 'names:%s' % SEQUENCE),
            ('foo', 'fred'),
            (END, ''),
            (END, ''),
            ('bar', 'joe'),
            ('year', '2012'),
        ]
        result = self._callFUT(fields)
        self.assertEqual(result, {'names': ['fred']})

    def test_spurious_nested_end(self):
        from peppercorn import END
        fields = self._getFields()
        index = fields.index(('month', '12'))
        self.assertEqual(index, 7)
        fields.insert(7, (END, ''))
        fields.insert(7, (END, ''))
        fields.insert(7, (END, ''))
        result = self._callFUT(fields)
        expected = {
            'series': {
                'dates': [['10']],
                'name': 'date series 1'},
            'month': '12',
            'year': '2008',
            'name': 'project1',
            'title': 'Cool project'}
        self.assertEqual(result, expected)

    def test_spurious_final_end(self):
        from peppercorn import START, RENAME, END
        fields = [
            (START, 'names:%s' % RENAME),
            ('foo', 'fred'),
            ('bar', 'joe'),
            (END, ''),
            (END, ''),
        ]
        result = self._callFUT(fields)
        self.assertEqual(result, {'names': 'fred'})


def encode_multipart_formdata(fields):
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(value)
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body
