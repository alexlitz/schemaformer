from __future__ import annotations
import logging
import json
from jsonschema import validate
import re
import os

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


def maybe_iter_properties(schema):
    if 'properties' in schema:
        for prop, prop_schema in schema['properties'].items():
            yield f'"{prop}":', prop_schema

def startswith_valid_end(json_str):
    return json_str.startswith('}') or json_str.startswith(']') or json_str.startswith(',') or json_str.startswith(' ') or json_str.startswith('\n') or json_str.startswith('\t') or json_str.startswith('\r')

def json_validate_prefix_object(json_str, schema):
    logger.debug(f'json_validate_prefix_object({repr(json_str)}, {schema})',) 
    if len(json_str) == 1:
        return 'properties' in schema, ""
    json_str = json_str[1:]
    atleast_one_prop = False
    all_props = False
    for prop_str, prop_schema in maybe_iter_properties(schema):
        if prop_str.startswith(json_str):
            return True, ""
        if json_str.startswith(prop_str):
            ok, json_str = json_validate_prefix_inner(json_str[len(prop_str):], prop_schema, return_remainder=True)
            if not ok:
                return ok, json_str
            atleast_one_prop = True
            if json_str.startswith(','):
                # FIXME not correct
                return False, json_str[1:]
            if json_str.startswith('}'):
                return True, json_str[1:]
            # FIXME not correct
            # return json_validate_prefix_object(json_str, schema)

    return atleast_one_prop, json_str

def json_validate_prefix_array(json_str, schema):
    logger.debug(f'json_validate_prefix_array({repr(json_str)}, {schema})')
    if json_str.startswith('['):
        if 'items' in schema:
            # FIXME
            return json_validate_prefix_inner(json_str[1:], schema['items'])
    return False, json_str

def prefix_matches_regex(json_str, pattern, is_full_str=False):
    if is_full_str:
        return re.fullmatch(pattern, json_str) is not None
    
    for i in range(len(pattern)):
        regex = re.compile(pattern[:len(pattern)-i])    
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

def json_validate_prefix_string(json_str, schema):
    logger.debug(f'json_validate_prefix_string({repr(json_str)}, {schema})')
    if 'pattern' in schema:
        json_str = json_str[1:] # Ignore the starting double-quote
        if len(json_str) == 0:
            return True, ""

        pattern = schema['pattern']
        S, json_str, is_full_str = maybe_get_full_string(json_str)
        ret, json_str = prefix_matches_regex(S, pattern, is_full_str), json_str
        return ret, json_str
        
    return False, json_str

def json_validate_prefix_boolean(json_str, schema):
    logger.debug(f'json_validate_prefix_boolean({repr(json_str)}, {schema})')
    if json_str.startswith('true'):
        return schema['type'] == 'boolean', json_str[4:]
    elif json_str.startswith('false'):
        return schema['type'] == 'boolean', json_str[5:]
    else:
        return False, json_str

def json_validate_prefix_null(json_str, schema):
    logger.debug(f'json_validate_prefix_null({repr(json_str)}, {schema})')
    if not json_str.startswith('null'):
        return False, json_str
    return schema['type'] == 'null', json_str[4:]

def json_validate_prefix_number(json_str, schema):
    logger.debug(f'json_validate_prefix_number({repr(json_str)}, {schema})')
    if json_str.startswith('-'):
        json_str = json_str[1:]

    seen_dot = False
    while json_str:
        if json_str[0] == '.':
            if seen_dot:
                return False, json_str
            seen_dot = True
        elif not json_str[0].isdigit():
            return False, json_str
        elif startswith_valid_end(json_str):
            break
        json_str = json_str[1:]
    
    return schema['type'] in ('number', 'integer'), json_str

def json_validate_prefix_inner(json_str, schema, return_remainder=False):
    json_str = json_str.lstrip()

    if len(json_str) == 0:
        return True, ""
    elif json_str.startswith('{'):
        return json_validate_prefix_object(json_str, schema)
    elif json_str.startswith('['):
        return json_validate_prefix_array(json_str, schema)
    elif json_str.startswith('"'):
        return json_validate_prefix_string(json_str, schema)
    elif json_str.startswith('t') or json_str.startswith('f'):
        return json_validate_prefix_boolean(json_str, schema)
    elif json_str.startswith('n'):
        return json_validate_prefix_null(json_str, schema)
    elif json_str.startswith('-') or json_str[0].isdigit():
        return json_validate_prefix_number(json_str, schema)
    else:
        return False, json_str

def json_validate_prefix(json_str, schema):
    ok, rem = json_validate_prefix_inner(json_str, schema)
    return ok and len(rem) == 0
