from __future__ import annotations
import logging
import json
from jsonschema import validate
import re
import os
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
    all_props = False
    l = list(maybe_iter_properties(schema))
    if len(l) == 0:
        return False, json_str
    
    d = dict(l)
    while len(d) > 0:
        for prop_str, prop_schema in d.items():
            if prop_str.startswith(json_str):
                return True, ""
            elif json_str.startswith(prop_str):
                ok, json_str = json_validate_prefix_inner(json_str[len(prop_str):], prop_schema, return_remainder=True)
                if not ok:
                    return ok, json_str
                if prop_str in required:
                    required.remove(prop_str)
                atleast_one_prop = True
                if json_str.startswith(','):
                    if len(json_str) == 1:
                        return False, json_str
                    json_str = json_str[1:]
                elif json_str.startswith('}'):
                    return len(required) == 0, json_str[1:]
                del d[prop_str]
                break
        else:
            break
        if len(d) == 0 or len(json_str) == 0:
            break

    return len(required) == 0, json_str

def json_validate_prefix_array(json_str, schema):
    logger.debug(f'json_validate_prefix_array({repr(json_str)}, {schema})')
    assert (schema['type'] == 'array')
    assert ('items' in schema)
    if not json_str.startswith('['):
        return False, json_str

    if 'uniqueItems' in schema:
        uniqueItems = schema['uniqueItems']
    
    if 'max_items' in schema:
        max_items = schema['max_items']
    else:
        max_items = None

    json_str = json_str[1:]
    if len(json_str) == 0:
        return True, json_str
    
    item_count = 0
    seen_items = set()
    while True:
        json_str_prev = json_str
        ok, json_str = json_validate_prefix_inner(json_str, schema['items'], return_remainder=True)
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
        S += json_str[:i+1]
        json_str = json_str[i+1:]
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

    ret = True;
    if 'format' in schema:
        pattern = format_to_pattern(schema['format'])
        ret, json_str = prefix_matches_regex(S, pattern, is_full_str), json_str
    elif 'pattern' in schema:
        pattern = schema['pattern']
        ret, json_str = prefix_matches_regex(S, pattern, is_full_str), json_str

    if len(json_str) == 0:
        return ret, ""
    elif is_full_str and startswith_valid_end(json_str):
        return ret, json_str[1:]
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

def json_validate_prefix_inner(json_str, schema, return_remainder=False):
    if json_str.startswith(" "):
        return False, json_str
    json_str = json_str.lstrip()
    schema_type = schema['type']
    if len(json_str) == 0:
        return True, ""
    elif schema_type == 'object':
        return json_validate_prefix_object(json_str, schema)
    elif schema_type == 'array':
        return json_validate_prefix_array(json_str, schema)
    elif schema_type == 'string':
        return json_validate_prefix_string(json_str, schema)
    elif schema_type == 'boolean':
        return json_validate_prefix_boolean(json_str, schema)
    elif schema_type == 'null':
        return json_validate_prefix_null(json_str, schema)
    elif schema_type in ('number', 'integer'):
        return json_validate_prefix_number(json_str, schema)
    else:
        return False, json_str

def json_validate_prefix(json_str, schema):
    ok, rem = json_validate_prefix_inner(json_str, schema)
    return ok and len(rem) == 0
