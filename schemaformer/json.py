from __future__ import annotations
import logging
import json
from jsonschema import validate
import re
import os
import copy
from itertools import count 

logger = logging.getLogger(__name__)

if os.environ.get('DEBUG', False):
    logger.setLevel(logging.DEBUG)
    # Create a StreamHandler to print the log messages to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create a Formatter for the log messages
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Set the Formatter for the StreamHandler
    console_handler.setFormatter(formatter)
    # Add the StreamHandler to the logger
    logger.addHandler(console_handler)

number_length_limit = 10
string_length_limit = 30

def maybe_iter_properties(schema):
    if 'properties' in schema:
        for prop, prop_schema in schema['properties'].items():
            yield f'"{prop}":', prop_schema

def startswith_valid_end(json_str):
    return json_str.startswith(('}', ']', ',', ' ', '\n', '\t', '\r'))

def json_validate_prefix_object(json_str, schema):
    logger.debug(f'json_validate_prefix_object({repr(json_str)}, {schema})',) 
    assert (schema['type'] == 'object')
    if not json_str.startswith('{'):
        return False, json_str
    if len(json_str) == 1:
        return 'properties' in schema, ""
    
    if 'required' in schema:
        required = set(schema['required'])
    else:
        required = set()
    
    json_str = json_str[1:]
    atleast_one_prop = False
    l = list(maybe_iter_properties(schema))
    if len(l) == 0:
        return False, json_str

    n_properties = len(l)
    n_properties_matched = 0
    
    d = dict(l)
    while len(d) > 0 or len(json_str) > 0:
        for prop_str, prop_schema in d.items():
            if not (len(d) > 0 or len(json_str) > 0):
                break
        
            if prop_str.startswith(json_str):
                return True, ""
            elif json_str.startswith(prop_str):
                ok, json_str = json_validate_prefix_inner(json_str[len(prop_str):], prop_schema)
                prop_str_name = prop_str[1:-2]
                if not ok:
                    return ok, json_str
                if prop_str_name in required:
                    required.remove(prop_str_name)
                del d[prop_str]
                n_properties_matched += 1
                if json_str.startswith(','):
                    if n_properties_matched == n_properties or len(d) == 0:
                        return False, json_str[1:]
                    json_str = json_str[1:]
                elif json_str.startswith('}'):
                    return len(required) == 0, json_str[1:]
                break
        else:
            break

    return True, json_str

def json_validate_prefix_array(json_str, schema):
    logger.debug(f'json_validate_prefix_array({repr(json_str)}, {schema})')
    assert (schema['type'] == 'array')
    assert ('items' in schema)
    if not json_str.startswith('['):
        return False, json_str

    if 'uniqueItems' in schema:
        uniqueItems = schema['uniqueItems']
    else:
        uniqueItems = False
    
    if 'max_items' in schema:
        max_items = schema['max_items']
    else:
        max_items = None

    json_str = json_str[1:]
    if len(json_str) == 0:
        return True, json_str
    
    item_count = 0
    seen_items = set()
    schema_items = schema['items']
    while True:
        json_str_prev = json_str
        ok, json_str = json_validate_prefix_inner(json_str, schema_items)
        if not ok:
            return ok, json_str
        if len(json_str) == 0:
            return True, json_str
        if uniqueItems:
            item_str = json_str_prev[:len(json_str_prev)-len(json_str)]
            # item_str = json.loads(json.dumps(item_str))
            if item_str in seen_items:
                return False, json_str
            seen_items.add(item_str) # Not the best way to do this, but it works for now

        item_count += 1
        if json_str.startswith(','):
            if max_items is not None and item_count >= max_items:
                return False, json_str
            if len(json_str) == 1:
                return True, json_str[1:]
            json_str = json_str[1:]
        if json_str.startswith(']'):
            break

    if 'min_items' in schema:
        min_items = schema['min_items']
        if item_count < min_items:
            return False, json_str
    
    return True, json_str

def prefix_matches_regex(json_str, pattern, is_full_str=False):
    if is_full_str:
        return re.fullmatch(pattern, json_str) is not None
    
    for i in range(len(pattern)):
        try:
            regex = re.compile(pattern[:len(pattern)-i])    
        except re.error:
            continue
        match = regex.search(json_str)
        if match and match.start() == 0 and match.end() == len(json_str):
            return True
    return False

def maybe_get_full_string(json_str):
    # Finds the end of a string, ignoring escaped double-quotes
    # Returns the string and the remainder of the json_str
    S = ""
    while True:
        i = json_str.find('"')
        if i == -1:
            break
        if i == 0 or json_str[i-1] != '\\':
            return S + json_str[:i], json_str[i+1:], True
        S += json_str[:i]
        json_str = json_str[i:]
    return S + json_str, "", False


def format_to_pattern(format):
    formats_dict = {
        "date-time": "^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\\.\\d+)?(Z|[+-][01][0-9]:[0-5][0-9])$",
        "email": "^[a-zA-Z0-9.!#$%&'*+\\/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\\.[a-zA-Z0-9-]+)*$",
        "hostname": "^(?=.{1,253})(?=.{1,63}(?:\\.|$))(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(?:\\.[a-zA-Z0-9-]{1,63}(?<!-))*$",
        "ipv4": "^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
        "ipv6": "^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$",
        "uri": "^(?:(?:https?|ftp):\\/\\/)(?:\\S+(?::\\S*)?@)?(?:(?:(?:[1-9]\\d?|1\\d\\d|2[01]\\d|22[0-3])(?:\\.(?:1?\\d{1,2}|2[0-4]\\d|25[0-5])){2}(?:\\.(?:[1-9]\\d?|1\\d\\d|2[0-4]\\d|25[0-4]))|(?:(?:[a-z\\u00a1-\\uffff0-9]-*)*[a-z\\u00a1-\\uffff0-9]+)(?:\\.(?:[a-z\\u00a1-\\uffff0-9]-*)*[a-z\\u00a1-\\uffff0-9]+)*(?:\\.(?:[a-z\\u00a1-\\uffff]{2,}))\\.?))(?::\\d{2,5})?(?:[/?#]\\S*)?$"
    }
    if format in formats_dict:
        return formats_dict[format]
    else:
        raise Exception(f"Unknown format: {format}")

def prefix_matches_format(json_str, format, is_full_str=False):
    pattern = format_to_pattern(format)
    if is_full_str:
        return re.fullmatch(pattern, json_str) is not None

    if format == "ipv4":
        S = "0.0.0.0"
    elif format == "ipv6":
        S = "0000:0000:0000:0000:0000:0000:0000:0000"
    elif format == "email":
        S = "a@gmail.com"
    elif format == "hostname":
        S = "a.com"
    # elif format == "date-time":
    #     S = "2020-01-01T00:00:00Z"
    # elif format == "uri":
    #     S = "http://a.com"
    else:
        raise Exception(f"Unknown format: {format}")

    for i in range(len(S)):
        if re.fullmatch(pattern, json_str + S[i:]) is not None:
            return True
    else:
        return False

def json_validate_prefix_string(json_str, schema):
    logger.debug(f'json_validate_prefix_string({repr(json_str)}, {schema})')
    assert (schema['type'] == 'string')
    if not json_str.startswith('"'):
        return False, json_str

    if 'maxLength' in schema:
        string_length_limit_local = min(schema['maxLength'], string_length_limit)
    else:
        string_length_limit_local = string_length_limit
    
    if 'minLength' in schema:
        min_length = schema['minLength']
    else:
        min_length = 0

    if 'enum' in schema:
        allowed_strings = schema['enum']
    else:
        allowed_strings = None
    
    json_str = json_str[1:] # Ignore the starting double-quote
    if len(json_str) == 0:
        return True, ""
    S, json_str, is_full_str = maybe_get_full_string(json_str)
    if len(S) > string_length_limit_local:
        return False, json_str
    if is_full_str and len(S) < min_length:
        return False, S + json_str
    
    if allowed_strings is not None:
        if is_full_str:
            return S in allowed_strings, json_str
        else:
            if not(any([s.startswith(S) for s in allowed_strings])):
                return False, json_str

    ret = True
    if 'format' in schema:
        ret = prefix_matches_format(S, schema['format'], is_full_str)
    if 'pattern' in schema:
        pattern = schema['pattern']
        ret = prefix_matches_regex(S, pattern, is_full_str)

    if len(json_str) == 0:
        return ret, ""
    elif is_full_str and startswith_valid_end(json_str):
        return ret, json_str
    else:
        return False, json_str

def json_validate_prefix_boolean(json_str, schema):
    logger.debug(f'json_validate_prefix_boolean({repr(json_str)}, {schema})')
    assert (schema['type'] == 'boolean')
    if json_str.startswith('true'):
        return True, json_str[4:]
    elif json_str.startswith('false'):
        return True, json_str[5:]
    else:
        return False, json_str

def json_validate_prefix_null(json_str, schema):
    logger.debug(f'json_validate_prefix_null({repr(json_str)}, {schema})')
    assert (schema['type'] == 'null')
    if json_str.startswith('null'):
        return True, json_str[4:]
    return False, json_str

def json_validate_prefix_number(json_str, schema):
    logger.debug(f'json_validate_prefix_number({repr(json_str)}, {schema})')
    if json_str.startswith('-'):
        json_str = json_str[1:]

    seen_dot = False
    for L in count():
        if len(json_str) == 0:
            break
        elif json_str[0] == '.':
            if seen_dot or schema['type'] == 'integer':
                return False, json_str
            seen_dot = True
        elif startswith_valid_end(json_str):
            json_str = json_str[1:]
            break
        elif not json_str[0].isdigit():
            return False, json_str
        json_str = json_str[1:]
        if L > number_length_limit:
            return False, json_str

    return schema['type'] in ('number', 'integer'), json_str

def hash_schema(schema):
    return hash(json.dumps(schema, sort_keys=True).encode('utf-8'))

cache = {}
def json_validate_prefix_inner(json_str, schema=None):
    global cache
    do_caching = False
    logger.debug(f'json_validate_prefix_inner({repr(json_str)}, {schema})')

    if do_caching:
        schema_hash = schema['schema_hash']
        key = hash((json_str, schema_hash))
        if key in cache:
            return cache[key]
        
    if json_str.startswith(" "):
        ret = (False, json_str)
    else:
        json_str = json_str.lstrip()
        schema_type = schema['type']
        if len(json_str) == 0:
            ret = (True, "")
        elif schema_type == 'object':
            ret = (json_validate_prefix_object(json_str, schema))
        elif schema_type == 'array':
            ret = (json_validate_prefix_array(json_str, schema))
        elif schema_type == 'string':
            ret = (json_validate_prefix_string(json_str, schema))
        elif schema_type == 'boolean':
            ret = (json_validate_prefix_boolean(json_str, schema))
        elif schema_type == 'null':
            ret = (json_validate_prefix_null(json_str, schema))
        elif schema_type in ('number', 'integer'):
            ret = (json_validate_prefix_number(json_str, schema))
        else:
            ret = (False, json_str)
    
    if do_caching:    
        cache[key] = ret
    return ret


def add_hashes_to_schema(schema):
    schema_hash = hash_schema(schema)
    if schema['type'] == 'object':
        for prop in schema['properties']:
            add_hashes_to_schema(schema['properties'][prop])
    elif schema['type'] == 'array':
        add_hashes_to_schema(schema['items'])
    schema['schema_hash'] = schema_hash

def json_validate_prefix(json_str, schema):
    logger.info(f'json_validate_prefix({repr(json_str)}, {schema})')
    ok, rem = json_validate_prefix_inner(json_str, schema)
    return ok and len(rem) == 0
